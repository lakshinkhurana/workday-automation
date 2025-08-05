"""
extraction.py

This module handles all scraping, parsing, and data fetching from the Workday UI.
It is responsible for navigating the site and extracting form element data into a 
structured format.
"""

import asyncio
import json
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from playwright.async_api import Page, ElementHandle
from filling import FormFiller
from mapping import DataMapper

# Configuration
DEFAULT_TIMEOUT = 30000

@dataclass
class PageInfo:
    """Information about a discovered page."""
    url: str
    path: str
    title: str = ""
    page_type: str = ""
    form_count: int = 0
    visited: bool = False

@dataclass
class FormElement:
    """Structured form element data."""
    label: str
    id_of_input_component: str
    name: str  # Added to store the 'name' attribute, crucial for radio groups
    required: bool
    type_of_input: str
    options: List[str] = field(default_factory=list)
    user_data_select_values: List[str] = field(default_factory=list)
    page_url: str = ""
    page_title: str = ""

class FormExtractor:
    """
    Extracts form elements from a given Playwright page.
    This is a refactored and simplified version of the original JSONExtractor.
    """

    async def extract_page_forms(self, page: Page, page_info: PageInfo) -> List[FormElement]:
        """Extracts all form elements from a single page, filtering out clutter."""
        print(f"  📝 Extracting forms from: {page_info.title}")
        page_forms = []
        await asyncio.sleep(5)  # Allow time for the page to load fully
        elements = await page.query_selector_all('input, select, textarea, button[type="button"], button[data-automation-id]')
        print(f"  🕵️‍♂️ Found {len(elements)} potential form elements. Analyzing structure:")

        for i, element in enumerate(elements):
            try:
                if await self._is_clutter_element(element):
                    continue

                element_id = await self._get_element_id(element)
                element_name = await element.get_attribute('name') or ''
                element_type = await self._get_input_type(element)
                element_label = await self._get_element_label(page, element)

                # For radio buttons, the label might be generic ("Yes"/"No"), so we try to find a more descriptive group label.
                if element_type == 'radio' and element_name:
                    # This is a simplified approach. A more robust solution might involve looking for a <fieldset> or a shared parent container.
                    group_label_element = await page.query_selector(f'[data-automation-id="formField-{element_name}"]')
                    if group_label_element:
                        element_label = await group_label_element.inner_text()


                form_element = FormElement(
                    label=element_label,
                    id_of_input_component=element_id or f"unidentified-{i}",
                    name=element_name,
                    required=await self._is_element_required(page, element),
                    type_of_input=element_type,
                    options=await self._get_element_options(element),
                    page_url=page_info.url,
                    page_title=page_info.title
                )
                
                page_forms.append(form_element)
                print(f"    - ✅ Added form element: '{form_element.label}' (type: {form_element.type_of_input}, name: {form_element.name})")
            
            except Exception as e:
                print(f"  ⚠️ Warning: Could not extract element {i+1}. Error: {e}")
                continue
        
        print(f"  📊 Total meaningful form elements extracted: {len(page_forms)}")
        return page_forms

    async def _is_clutter_element(self, element: ElementHandle) -> bool:
        """Identifies and filters out clutter elements that aren't meaningful form inputs."""
        try:
            tag_name = (await element.evaluate('el => el.tagName')).lower()
            element_id = await element.get_attribute('id') or ""
            data_automation_id = await element.get_attribute('data-automation-id') or ""
            element_class = await element.get_attribute('class') or ""
            element_type = await element.get_attribute('type') or ""

            # Check for aria-hidden attribute
            if await element.get_attribute('aria-hidden') == 'true':
                return True

            # Check for CSS visibility (display: none or visibility: hidden)
            # This is a more robust check than just is_visible() which might not catch all cases
            style_display = await element.evaluate('el => window.getComputedStyle(el).display')
            style_visibility = await element.evaluate('el => window.getComputedStyle(el).visibility')
            if style_display == 'none' or style_visibility == 'hidden':
                return True
            
            # Navigation and UI control elements to exclude
            navigation_keywords = [
                'next', 'continue', 'back', 'previous', 'save', 'submit', 'close', 'cancel',
                'pageFooter', 'navigation', 'breadcrumb', 'menu', 'header', 'footer',
                'modal', 'dialog', 'popup', 'tooltip', 'dropdown-toggle', 'collapse',
                'accordion', 'tab', 'sidebar', 'overlay', 'backdrop','settings','account','hammy',
            ]
            
            # UI state and control elements
            ui_control_keywords = [
                'search', 'filter', 'sort', 'pagination', 'scroll', 'resize',
                'toggle', 'switch', 'checkbox-all', 'select-all', 'expand', 'minimize'
            ]
            
            # Hidden or technical elements
            hidden_keywords = [
                'hidden', 'csrf', 'token', 'session', 'tracking', 'analytics',
                'autocomplete-off', 'captcha', 'honeypot' , 'jobposting'
            ]
            
            # Combine all clutter keywords
            clutter_keywords = navigation_keywords + ui_control_keywords + hidden_keywords
            
            # Check data-automation-id for clutter patterns
            for keyword in clutter_keywords:
                if keyword.lower() in data_automation_id.lower():
                    return True
            
            # Check element id for clutter patterns
            for keyword in clutter_keywords:
                if keyword.lower() in element_id.lower():
                    return True
            
            # Check class names for common UI framework clutter
            clutter_class_patterns = [
                'btn-secondary', 'btn-outline', 'btn-ghost', 'btn-link',
                'nav-', 'navbar-', 'breadcrumb-', 'dropdown-', 'modal-',
                'tooltip-', 'popover-', 'accordion-', 'tab-', 'sidebar-'
            ]
            
            for pattern in clutter_class_patterns:
                if pattern in element_class:
                    return True
            
            # Filter out specific input types that are usually not form data
            if tag_name == 'input':
                clutter_input_types = ['hidden', 'submit', 'reset', 'button', 'image']
                if element_type in clutter_input_types:
                    return True
            
            # Filter out buttons that are clearly navigation/UI controls
            if tag_name == 'button':
                # Get button text to check content
                try:
                    button_text = await element.inner_text()
                    button_text_lower = button_text.lower().strip()
                    
                    navigation_text = [
                        'next', 'continue', 'back', 'previous', 'save', 'submit',
                        'close', 'cancel', 'ok', 'done', 'finish', 'skip'
                    ]
                    
                    # If button text matches navigation keywords, it's likely clutter
                    if button_text_lower in navigation_text:
                        return True
                    
                    # However, keep buttons that are clearly for file operations or data input
                    keep_button_keywords = [
                        'select file', 'upload', 'browse', 'choose file', 'add file',
                        'attach', 'select files', 'browse files'
                    ]
                    
                    for keyword in keep_button_keywords:
                        if keyword in button_text_lower:
                            return False  # Don't filter out these buttons
                    
                except Exception:
                    pass  # If we can't get button text, continue with other checks
            
            # Check if element has very small dimensions (likely hidden UI elements)
            try:
                bounding_box = await element.bounding_box()
                if bounding_box and (bounding_box['width'] < 10 or bounding_box['height'] < 10):
                    return True
            except Exception:
                pass
            
            return False
            
        except Exception as e:
            print(f"    - Warning: Error checking if element is clutter: {e}")
            return False  # If we can't determine, don't filter it out

    async def _get_element_id(self, element: ElementHandle) -> str:
        """Gets a unique identifier for a form element."""
        # Prioritize data-automation-id, then id, then name
        for attr in ['data-automation-id', 'id', 'name']:
            value = await element.get_attribute(attr)
            if value:
                return value
        return ""

    async def _get_element_label(self, page: Page, element: ElementHandle) -> str:
        """Gets the label associated with a form element."""
        element_id = await element.get_attribute('id')
        if element_id:
            label = await page.query_selector(f'label[for="{element_id}"]')
            if label:
                return await label.inner_text()
        
        # Fallback strategies
        for attr in ['aria-label', 'placeholder']:
            value = await element.get_attribute(attr)
            if value:
                return value

        # Check parent text content as a last resort
        parent = await element.query_selector('xpath=..')
        if parent:
            parent_text = await parent.inner_text()
            cleaned_text = ' '.join(parent_text.split())
            if len(cleaned_text) < 100: # Avoid overly long labels
                return cleaned_text

        return "Unlabeled Field"

    async def _get_input_type(self, element: ElementHandle) -> str:
      """Determines the type of an input element."""
      tag_name = (await element.evaluate('el => el.tagName')).lower()
    
      if tag_name == 'input':
        return (await element.get_attribute('type') or 'text').lower()
      elif tag_name == 'select':
        return 'select'
      elif tag_name == 'textarea':
        return 'textarea'
      elif tag_name == 'button':
        # Check for specific button types
        button_type = await element.get_attribute('type')
        data_automation_id = await element.get_attribute('data-automation-id')
        
        # Handle file selection buttons
        if data_automation_id and 'select-files' in data_automation_id:
            return 'file-selector'
        elif data_automation_id and 'file' in data_automation_id.lower():
            return 'file-related'
        elif await element.get_attribute('aria-haspopup') == 'listbox':
            return 'dropdown'
        elif button_type == 'button':
            return 'button'
        else:
            return f'button-{button_type}' if button_type else 'button'
    
      return tag_name
    
    async def _is_element_required(self, page: Page, element: ElementHandle) -> bool:
        """Checks if a form element is marked as required."""
        if await element.get_attribute('required') is not None:
            return True
        if await element.get_attribute('aria-required') == 'true':
            return True
        
        label = await self._get_element_label(page, element)
        if '*' in label:
            return True
            
        return False

    async def _get_element_options(self, element: ElementHandle) -> List[str]:
        """Gets available options for select, radio, or dropdown elements."""
        options = []
        input_type = await self._get_input_type(element)

        if input_type == 'select':
            option_elements = await element.query_selector_all('option')
            for opt in option_elements:
                text = await opt.inner_text()
                if text.strip():
                    options.append(text.strip())
        return options


class WorkdayScraper:
    """
    Handles the navigation and scraping of the Workday application pages.
    This is a refactored and focused version of the original WorkdayFormScraper.
    """
    def __init__(self, tenant_url: str):
        self.tenant_url = tenant_url
        self.form_extractor = FormExtractor()
        self.discovered_pages: List[PageInfo] = []
        self.form_elements: List[FormElement] = []
        self.processed_steps: set = set()

    async def scrape_site(self, page: Page) -> List[FormElement]:
        """
        Main scraping orchestration method.
        Navigates through the application process and extracts form data.
        """
        print("🌐 Phase 1: Navigating to initial page and finding job.")
        await page.goto(self.tenant_url, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle")

        if not await self._click_job_title_link(page):
            print("❌ Error: Could not find a job title link to start the process.")
            return []

        print("\n🔒 Phase 2: Clicking Apply and handling login/account creation.")
        if not await self._click_apply_button(page):
            print("❌ Error: Could not find or click the 'Apply' button.")
            return []

        # After applying, we expect a login/create account page.
        filler = FormFiller()
        if not await filler.create_account(page):
            print("❌ Error: Account creation failed. The process cannot continue.")
            return []
          
        await asyncio.sleep(5)  # Allow time for the page to settle after account creation
        
        print("\n🔍 Phase 3: Traversing and extracting from application forms.")
        await self._traverse_and_extract(page)

        print(f"\n✅ Extraction Complete. Found {len(self.form_elements)} form elements across {len(self.discovered_pages)} pages.")
        return self.form_elements

    async def _click_job_title_link(self, page: Page) -> bool:
        """Finds and clicks the first available job title link."""
        # Simplified selector for job titles
        job_selector = '[data-automation-id="jobTitle"]'
        try:
            await page.wait_for_selector(job_selector, timeout=10000)
            job_elements = await page.query_selector_all(job_selector)
            if job_elements:
                await job_elements[0].click()
                await page.wait_for_load_state("networkidle")
                print("  ✅ Successfully clicked job title.")
                return True
        except Exception as e:
            print(f"  ⚠️ Warning: Could not click job title link. {e}")
        return False

    async def _click_apply_button(self, page: Page) -> bool:
        """Finds and clicks the 'Apply' button, then 'Apply Autofill with Resume'."""
        try:
            # Simplified: Clicks the first button that looks like "Apply"
            apply_selector = '[data-automation-id="adventureButton"]'
            await page.wait_for_selector(apply_selector, timeout=10000)
            await page.click(apply_selector)
            await page.wait_for_load_state("networkidle", timeout=5000)
            
            # After clicking "Apply", a dialog often appears. We'll choose "Apply Manually".
            manual_apply_selector = '[data-automation-id="autofillWithResume"]'
            await page.wait_for_selector(manual_apply_selector, timeout=5000)
            await page.click(manual_apply_selector)
            await page.wait_for_load_state("networkidle")
            print("  ✅ Successfully clicked 'Apply' and 'Autofill with Resume'.")
            return True
        except Exception as e:
            print(f"  ⚠️ Warning: Could not complete the apply process. {e}")
            # It might be that we are already on the application page
            return True

    async def _is_self_identity_page(self, page: Page) -> bool:
        """Check if the current page is the Self Identity page"""
        try:
            # Look for unique identifiers of the Self Identity page
            indicators = [
                '[data-automation-id*="selfIdentifiedDisabilityData"]',
                'input[id*="selfIdentifiedDisabilityData"]',
                'text="Self Identification"',
                'text="Disability Status"',
                'text="Voluntary Self-Identification"'
            ]
          
            for indicator in indicators:
              element = page.locator(indicator).first
              if await element.is_visible():
                  print(f"    ✅ Found Self Identity page indicator: {indicator}")
                  return True
            return False
        except Exception as e:
          print(f"    ❌ Error checking for Self Identity page: {str(e)}")
          return False

    async def _handle_self_identity_page(self, page: Page) -> bool:
        """Handle Self Identify page - fill name, date, checkboxes and press Save and Continue"""
        print("  📊 Processing Self Identity page...")
        
        try:
            # Use a more robust selector that checks id, data-automation-id, and name
            name_locator = page.locator(
                '[data-automation-id="selfIdentifiedDisabilityData--name"], ' \
                '[id="selfIdentifiedDisabilityData--name"], ' \
                '[name="selfIdentifiedDisabilityData--name"]'
            ).first
            
            # Wait for the element to be ready before proceeding
            await name_locator.wait_for(timeout=15000)

            today = datetime.now()
            
            # Fill name field
            legal_name = os.getenv('LEGAL_NAME', '')
            if legal_name:
                await name_locator.fill(legal_name)
                print("    ✅ Filled name field.")

            # Fill date fields
            await page.locator('[id="selfIdentifiedDisabilityData--dateSignedOn-dateSectionMonth-input"]').fill(str(today.month))
            await page.locator('[id="selfIdentifiedDisabilityData--dateSignedOn-dateSectionDay-input"]').fill(str(today.day))
            await page.locator('[id="selfIdentifiedDisabilityData--dateSignedOn-dateSectionYear-input"]').fill(str(today.year))
            print("    ✅ Filled date fields.")

            # Handle disability checkboxes
            preferred_option = os.getenv('DISABILITY_STATUS', 'no answer').lower()
            
            disability_options = {
                "no answer": [
                    "I do not wish to answer",
                    "I do not want to answer",
                    "I prefer not to answer",
                    "Choose not to identify",
                    "Decline to answer",
                    "Prefer not to disclose",
                    "Do not wish to identify"
                ],
                "yes": [
                    "Yes, I have a disability, or have had one in the past",
                    "Yes",
                    "I have a disability",
                    "Person with disability"
                ],
                "no": [
                    "No, I don't have a disability and have not had one in the past",
                    "No",
                    "I do not have a disability",
                    "No disability"
                ]
            }

            options_to_try = disability_options.get(preferred_option, disability_options["no answer"])

            for option_text in options_to_try:
                try:
                    # Using a more robust selector to find the label and then the associated radio button
                    label_locator = page.locator(f'label:has-text("{option_text}")')
                    if await label_locator.is_visible():
                        await label_locator.click()
                        print(f"      ✅ Clicked option: '{option_text}'")
                        break
                except Exception:
                    continue
            
            # Press Save and Continue
            nav_selector = 'button[data-automation-id="pageFooterNextButton"], button:has-text("Continue"), button:has-text("Save and Continue")'
            nav_button = page.locator(nav_selector).first
            if await nav_button.is_visible():
                await nav_button.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
                print("    ✅ Clicked 'Save and Continue'.")
                return True
            else:
                print("    ⚠️ Could not find 'Save and Continue' button.")
                return False
                
        except Exception as e:
            print(f"  ❌ Error handling Self Identity page: {str(e)}")
            return False

    async def _traverse_and_extract(self, page: Page):
        """
        Traverses the application flow by tracking the active step in the progress bar,
        extracting, mapping, and filling one step at a time.
        """
        max_steps = 10  # Safety break to prevent infinite loops
        data_mapper = DataMapper()
        form_filler = FormFiller()

        for _ in range(max_steps):
            try:
                # Check if we are on the self-identity page
                if await self._is_self_identity_page(page):
                    if await self._handle_self_identity_page(page):
                        continue
                    else:
                        print("  🛑 Failed to handle the Self Identity page. Ending traversal.")
                        break

                # 1. Identify the current active step
                active_step_locator = page.locator('[data-automation-id="progressBarActiveStep"]')
                await active_step_locator.wait_for(timeout=10000)
                active_step_text = await active_step_locator.inner_text()

                if active_step_text in self.processed_steps:
                    print(f"  ✅ Reached a previously processed step ('{active_step_text}'). Ending traversal.")
                    break
                
                # The wait for the active step locator at the start of the loop is sufficient.
                # The sleep(3) is removed for more reliable waiting.
                print(f"📄 Processing step: {active_step_text}")

                # 2. Extract forms from the current step
                page_info = PageInfo(
                    url=page.url,
                    path=active_step_text,
                    title=await page.title(),
                    visited=True
                )
                extracted_elements = await self.form_extractor.extract_page_forms(page, page_info)
                self.form_elements.extend(extracted_elements)
                self.discovered_pages.append(page_info)
                self.processed_steps.add(active_step_text)

                # 3. Map and Fill the extracted data for the current step
                if extracted_elements:
                    mapped_fields = data_mapper.map_data_to_form_elements([e.__dict__ for e in extracted_elements])
                    if mapped_fields:
                        await form_filler.fill_fields_on_current_page(page, mapped_fields)
                    else:
                        print("  ℹ️ No data to fill for the current step.")
                else:
                    print("  ℹ️ No form elements found on this step.")

                # 4. Navigate to the next step
                nav_selector = 'button[data-automation-id="pageFooterNextButton"], button:has-text("Continue"), button:has-text("Save and Continue")'
                nav_button = page.locator(nav_selector).first
                if await nav_button.is_visible():
                    previous_step_text = active_step_text
                    await nav_button.click(force=True)
                    print('😴 Sleeping till loaded ')
                    await asyncio.sleep(10)
                    
                    # Wait for the page to transition by checking that the active step has changed.
                    # This is more reliable than waiting for network idle.
                    print(f"  → Clicked 'Continue'. Waiting for next step after '{previous_step_text.replace('', '')}'...")
                    # Sanitize the text for the CSS selector by wrapping it in quotes using json.dumps.
                    sanitized_step_text = json.dumps(previous_step_text)
                    await page.locator(f"[data-automation-id='progressBarActiveStep']:not(:text-is({sanitized_step_text}))").wait_for(timeout=20000)
                    print("  ✅ Next step loaded.")
                else:
                    print("  🛑 No 'Continue' or 'Next' button found. Ending traversal.")
                    break

            except Exception as e:
                print(f"  🛑 An error occurred during traversal: {e}. Ending traversal.")
                break
