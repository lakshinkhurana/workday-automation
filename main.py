#!/usr/bin/env python3
"""
Workday Job Application Form Extractor
Author: Web Automation Engineer
Date: 2025-01-22
Description: 
Navigate to a job posting, click Apply, and extract form elements as JSON.
"""

import os
import json
import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

# Load environment variables
load_dotenv()

# Configuration constants
OUTPUT_FILE = "workday_forms_complete.json"
DEFAULT_TIMEOUT = 30000

@dataclass
class PageInfo:
    """Information about a discovered page"""
    url: str
    path: str
    title: str = ""
    page_type: str = ""
    form_count: int = 0
    visited: bool = False

@dataclass
class FormElement:
    """Structured form element data"""
    label: str
    id_of_input_component: str
    required: bool
    type_of_input: str
    options: List[str] = field(default_factory=list)
    user_data_select_values: List[str] = field(default_factory=list)
    page_url: str = ""
    page_title: str = ""

@dataclass
class ExtractionResults:
    """Complete extraction results with metadata"""
    form_elements: List[Dict[str, Any]]
    pages_visited: List[PageInfo]
    total_pages_crawled: int
    total_form_elements: int
    extraction_timestamp: float
    tenant_url: str
    errors: List[str] = field(default_factory=list)

class WorkdayFormScraper:
    """Main scraper class for job application form extraction"""
    
    def __init__(self):
        self.discovered_pages: List[PageInfo] = []
        self.form_elements: List[FormElement] = []
        self.errors: List[str] = []
        self.tenant_url = os.getenv('WORKDAY_TENANT_URL', '')
        
    async def run(self) -> ExtractionResults:
        """Main execution flow - Navigate to job and extract form elements"""
        print("🚀 Starting Workday Job Application Form Extractor")
        print("=" * 60)
        
        if not self.tenant_url:
            raise ValueError("Missing required environment variable: WORKDAY_TENANT_URL")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()
            page.set_default_timeout(DEFAULT_TIMEOUT)
            
            try:
                # Phase 1: Navigate to initial page
                print("\n📍 Phase 1: Navigating to Initial Page")
                await page.goto(self.tenant_url, wait_until="domcontentloaded")
                await page.wait_for_load_state("networkidle", timeout=15000)
                
                # Phase 2: Find and click job title link
                print("\n📍 Phase 2: Finding Job Title Link")
                job_clicked = await self._click_job_title_link(page)
                
                if not job_clicked:
                    print("  ❌ No job title link found")
                    return await self._create_results()
                
                # Phase 3: Handle login page
                print("\n📍 Phase 3: Handling Login Page")
                login_success = await self._handle_login_page(page)
                
                if not login_success:
                    print("  ⚠️ Login not successful, but continuing with form extraction")
                
                # Phase 4: Extract form elements from pages
                print("\n📍 Phase 4: Extracting Form Elements")
                await self._extract_application_forms(page)
                
                # Phase 4: Create and save results
                print(f"\n📍 Extraction Complete")
                print(f"  Pages visited: {len(self.discovered_pages)}")
                print(f"  Form elements extracted: {len(self.form_elements)}")
                
                results = await self._create_results()
                await self._save_results(results)
                
                return results
                
            except Exception as e:
                self.errors.append(f"Critical error: {str(e)}")
                print(f"❌ Critical error: {str(e)}")
                
                # Return partial results
                return await self._create_results()
                
            finally:
                await browser.close()
    
    async def _click_job_title_link(self, page: Page) -> bool:
        """Find and click any link with data-automation-id='jobTitle'"""
        print("  🔍 Looking for job title links...")
        
        job_title_selectors = [
            '[data-automation-id="jobTitle"]',
            '[data-automation-id="jobTitle"] a',
            'a[data-automation-id="jobTitle"]'
        ]
        
        for selector in job_title_selectors:
            try:
                # Find all job title elements
                job_elements = await page.query_selector_all(selector)
                print(f"  🔍 Found {len(job_elements)} job title elements with selector: {selector}")
                
                if job_elements:
                    # Click the first job title link
                    first_job = job_elements[0]
                    
                    # If it's a container, look for the link inside
                    if selector == '[data-automation-id="jobTitle"]':
                        link_element = await first_job.query_selector('a')
                        if link_element:
                            first_job = link_element
                    
                    job_title = await first_job.inner_text()
                    print(f"  ✅ Found job title: '{job_title[:50]}...'")
                    
                    await first_job.click()
                    print("  🖱️ Clicked job title link")
                    
                    # Wait for job page to load
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    await asyncio.sleep(2)
                    return True
                    
            except Exception as e:
                print(f"  ⚠️ Error with selector {selector}: {str(e)}")
                continue
        
        print("  ❌ No job title links found")
        return False
    
    async def _handle_login_page(self, page: Page) -> bool:
        """Handle login page that appears after clicking job title"""
        print("  🔍 Checking if login is required...")
        
        # Check if we're on a login page
        login_indicators = [
            'input[type="email"]',
            'input[data-automation-id="email"]',
            'button:has-text("Sign In")',
            'text="Sign In"',
            '.login-form',
            '[data-automation-id="utilityButtonSignIn"]'
        ]
        
        login_needed = False
        for indicator in login_indicators:
            try:
                if await page.query_selector(indicator):
                    login_needed = True
                    print(f"  ✅ Login page detected (found: {indicator})")
                    break
            except:
                continue
        
        if not login_needed:
            print("  ℹ️ No login required, proceeding with form extraction")
            return True
        
        # If login is needed, try to find Apply button or continue without login
        print("  🔍 Login page detected, looking for Apply button...")
        
        # Look for Apply button on login page
        apply_found = await self._click_apply_button(page)
        
        if apply_found:
            print("  ✅ Found and clicked Apply button on login page")
            return True
        
        # If no Apply button, look for other ways to access forms
        print("  🔍 No Apply button found, looking for alternative access...")
        
        # Try to find registration or guest access options
        guest_selectors = [
            'a:has-text("Continue as Guest")',
            'a:has-text("Apply Without Account")',
            'button:has-text("Continue as Guest")',
            '[data-automation-id="guestAccess"]',
            '[data-automation-id="continueAsGuest"]'
        ]
        
        for selector in guest_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=3000, state='visible')
                if element:
                    await element.click()
                    print(f"  ✅ Clicked guest access: {selector}")
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    return True
            except:
                continue
        
        print("  ⚠️ Login page detected but no way to proceed without credentials")
        return False
    
    async def _click_apply_button(self, page: Page) -> bool:
        """Find and click the Apply button, then click Apply Manually"""
        print("  🔍 Looking for Apply button...")
        
        apply_selectors = [
            'button:has-text("Apply")',
            'a:has-text("Apply")',
            'button[data-automation-id*="apply"]',
            'a[data-automation-id*="apply"]',
            'button:has-text("Apply for this Job")',
            'a:has-text("Apply for this Job")',
            '.apply-button',
            '#apply-button'
        ]
        
        # Step 1: Click the main Apply button
        apply_clicked = False
        for selector in apply_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=5000, state='visible')
                if element:
                    button_text = await element.inner_text()
                    print(f"  ✅ Found Apply button: '{button_text}'")
                    await element.click()
                    print("  🖱️ Clicked Apply button")
                    
                    # Wait for application options to load
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    await asyncio.sleep(2)
                    apply_clicked = True
                    break
            except:
                continue
        
        if not apply_clicked:
            print("  ⚠️ No Apply button found")
            return False
        
        # Step 2: Look for and click Apply Manually button
        print("  🔍 Looking for Apply Manually button...")
        
        apply_manually_selectors = [
            '[data-automation-id="applyManually"]',
            'button[data-automation-id="applyManually"]',
            'a[data-automation-id="applyManually"]',
            'button:has-text("Apply Manually")',
            'a:has-text("Apply Manually")',
            'button:has-text("Manual Application")',
            'a:has-text("Manual Application")'
        ]
        
        for selector in apply_manually_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=5000, state='visible')
                if element:
                    button_text = await element.inner_text()
                    print(f"  ✅ Found Apply Manually button: '{button_text}'")
                    await element.click()
                    print("  🖱️ Clicked Apply Manually button")
                    
                    # Wait for login page to load
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    await asyncio.sleep(2)
                    return True
            except:
                continue
        
        print("  ⚠️ No Apply Manually button found, but Apply was clicked")
        return True  # Return true since we at least clicked Apply
    
    async def _extract_application_forms(self, page: Page):
        """Extract form elements from application pages"""
        print("  📋 Extracting form elements from current page...")
        
        # Create page info for current page
        current_url = page.url
        page_title = await page.title()
        page_info = PageInfo(
            url=current_url,
            path=current_url.replace(self.tenant_url, '') or '/',
            title=page_title,
            page_type="Job Application",
            visited=True
        )
        
        # Extract forms from current page
        page_forms = await self._extract_page_forms(page, page_info)
        page_info.form_count = len(page_forms)
        self.form_elements.extend(page_forms)
        self.discovered_pages.append(page_info)
        
        print(f"  ✅ Extracted {len(page_forms)} form elements from current page")
        
        # Look for additional application pages (My Information, EEO, Review, etc.)
        await self._traverse_application_flow(page)
    
    async def _traverse_application_flow(self, page: Page):
        """Traverse through application flow pages"""
        print("  🔍 Looking for additional application pages...")
        
        # Common application flow navigation
        nav_selectors = [
            'a:has-text("My Information")',
            'a:has-text("Job Application")', 
            'a:has-text("EEO")',
            'a:has-text("Review")',
            'a:has-text("Next")',
            'a:has-text("Continue")',
            'button:has-text("Next")',
            'button:has-text("Continue")',
            '[data-automation-id*="next"]',
            '[data-automation-id*="continue"]'
        ]
        
        visited_pages = {page.url}
        pages_processed = 1
        max_pages = 5
        
        while pages_processed < max_pages:
            # Look for navigation links
            nav_found = False
            
            for selector in nav_selectors:
                try:
                    nav_element = await page.wait_for_selector(selector, timeout=3000, state='visible')
                    if nav_element:
                        nav_text = await nav_element.inner_text()
                        print(f"  🔗 Found navigation: {nav_text}")
                        
                        await nav_element.click()
                        await page.wait_for_load_state("networkidle", timeout=8000)
                        await asyncio.sleep(2)
                        
                        # Check if we're on a new page
                        new_url = page.url
                        if new_url not in visited_pages:
                            visited_pages.add(new_url)
                            
                            # Extract forms from new page
                            page_title = await page.title()
                            page_info = PageInfo(
                                url=new_url,
                                path=new_url.replace(self.tenant_url, '') or '/',
                                title=page_title,
                                page_type=self._classify_page_type(new_url, page_title),
                                visited=True
                            )
                            
                            page_forms = await self._extract_page_forms(page, page_info)
                            page_info.form_count = len(page_forms)
                            self.form_elements.extend(page_forms)
                            self.discovered_pages.append(page_info)
                            
                            print(f"  ✅ Page {pages_processed + 1}: Extracted {len(page_forms)} form elements")
                            pages_processed += 1
                            nav_found = True
                            break
                        else:
                            print(f"  ℹ️ Already visited this page")
                            
                except:
                    continue
            
            if not nav_found:
                print("  ℹ️ No more navigation found")
                break
        
        print(f"  ✅ Application flow traversal complete: {pages_processed} pages processed")
    
    def _classify_page_type(self, path: str, title: str) -> str:
        """Classify page type based on URL path and title"""
        path_lower = path.lower()
        title_lower = title.lower()
        
        if any(keyword in path_lower for keyword in ['/myaccount/', '/profile/', '/information/']):
            return "My Information"
        elif any(keyword in path_lower for keyword in ['/application/', '/apply/', '/job/']):
            return "Job Application"
        elif any(keyword in path_lower for keyword in ['/eeo/', '/equal/', '/opportunity/']):
            return "EEO"
        elif any(keyword in path_lower for keyword in ['/review/', '/summary/', '/confirm/']):
            return "Review"
        else:
            return "Other"
    
    async def _extract_page_forms(self, page: Page, page_info: PageInfo) -> List[FormElement]:
        """Extract all form elements from current page"""
        form_elements = []
        
        try:
            # Wait for dynamic content to load
            await asyncio.sleep(2)
            
            # Find form containers using multiple strategies
            containers = await self._find_form_containers(page)
            
            print(f"    🔍 Found {len(containers)} form containers")
            
            for container in containers:
                try:
                    # Skip invisible elements
                    if not await container.is_visible():
                        continue
                    
                    # Identify form control type
                    control_type = await self._identify_control_type(container)
                    if not control_type:
                        continue
                    
                    # Extract element data
                    label = await self._extract_label(container)
                    identifier = await self._extract_identifier(container)
                    required = await self._is_required(container)
                    
                    # Extract options for multi-choice controls
                    options = []
                    if control_type in ("select", "multiselect", "radio", "checkbox"):
                        options = await self._extract_options(container, control_type)
                    
                    # Generate sample values
                    sample_values = self._generate_sample_values(control_type, options, label)
                    
                    # Handle special cases
                    if control_type == "date":
                        options = ["MM", "DD", "YYYY"]
                        sample_values = ["01", "15", "2024"]
                    elif control_type == "file":
                        sample_values = ["resume.pdf"]
                    
                    # Create form element
                    form_element = FormElement(
                        label=label,
                        id_of_input_component=identifier,
                        required=required,
                        type_of_input=control_type,
                        options=options,
                        user_data_select_values=sample_values,
                        page_url=page_info.url,
                        page_title=page_info.title
                    )
                    
                    form_elements.append(form_element)
                    
                except Exception as e:
                    # Skip problematic elements but continue processing
                    continue
        
        except Exception as e:
            error_msg = f"Error extracting forms from {page_info.url}: {str(e)}"
            self.errors.append(error_msg)
            print(f"    ❌ {error_msg}")
        
        return form_elements
    
    async def _find_form_containers(self, page: Page) -> List:
        """Find all form containers and individual form elements"""
        containers = []
        
        # Strategy 1: Workday-specific containers
        workday_containers = await page.query_selector_all('.WDSC-FormField, [data-automation-id="formField"]')
        containers.extend(workday_containers)
        
        # Strategy 2: Generic form containers
        generic_containers = await page.query_selector_all('form, .form-group, .form-field, .input-group')
        containers.extend(generic_containers)
        
        # Strategy 3: Direct form elements (always include these)
        direct_elements = await page.query_selector_all('input, select, textarea, button[type="submit"], button[data-automation-id*="submit"], button[data-automation-id*="Button"]')
        containers.extend(direct_elements)
        
        # Strategy 4: Specific login/registration form elements
        login_elements = await page.query_selector_all(
            'input[type="email"], input[type="password"], input[data-automation-id="email"], '
            'input[data-automation-id="password"], input[data-automation-id="verifyPassword"], '
            'button[data-automation-id="createAccountSubmitButton"], button[data-automation-id="signInSubmitButton"]'
        )
        containers.extend(login_elements)
        
        # Remove duplicates while preserving order
        unique_containers = []
        seen = set()
        for container in containers:
            try:
                container_id = await container.evaluate('el => el.outerHTML')
                if container_id not in seen:
                    seen.add(container_id)
                    unique_containers.append(container)
            except:
                # If we can't get outerHTML, just add it anyway
                unique_containers.append(container)
        
        return unique_containers
    
    async def _identify_control_type(self, element) -> Optional[str]:
        """Identify form control type"""
        try:
            tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
            
            if tag_name == 'input':
                input_type = await element.get_attribute('type') or 'text'
                type_mapping = {
                    'text': 'text', 'email': 'text', 'tel': 'text', 'number': 'text',
                    'password': 'password', 'file': 'file', 'checkbox': 'checkbox',
                    'radio': 'radio', 'submit': 'submit', 'date': 'date', 'search': 'text'
                }
                return type_mapping.get(input_type, 'text')
            
            elif tag_name == 'textarea':
                return 'textarea'
            
            elif tag_name == 'select':
                multiple = await element.get_attribute('multiple')
                return 'multiselect' if multiple else 'select'
            
            elif tag_name == 'button':
                button_type = await element.get_attribute('type') or 'button'
                return 'submit' if button_type == 'submit' else None
            
            # Handle container elements
            else:
                # Check for child form controls
                if await element.query_selector('input[type="text"], input[type="email"], input[type="search"]'):
                    return 'text'
                elif await element.query_selector('input[type="password"]'):
                    return 'password'
                elif await element.query_selector('textarea'):
                    return 'textarea'
                elif await element.query_selector('input[type="file"]'):
                    return 'file'
                elif await element.query_selector('input[type="checkbox"]'):
                    return 'checkbox'
                elif await element.query_selector('input[type="radio"]'):
                    return 'radio'
                elif await element.query_selector('select'):
                    select_elem = await element.query_selector('select')
                    multiple = await select_elem.get_attribute('multiple')
                    return 'multiselect' if multiple else 'select'
                elif await element.query_selector('div[role="combobox"]'):
                    return 'select'
                elif await element.query_selector('[data-automation-id*="date"], input[type="date"]'):
                    return 'date'
        
        except Exception:
            pass
        
        return None
    
    async def _extract_label(self, element) -> str:
        """Extract label using multiple strategies"""
        try:
            # Strategy 1: Workday-specific label selectors
            label_selectors = [
                '[data-automation-id="label"]',
                '.WDSC-Label',
                '.gwt-Label',
                'label'
            ]
            
            for selector in label_selectors:
                label_element = await element.query_selector(selector)
                if label_element:
                    label_text = await label_element.inner_text()
                    if label_text.strip():
                        # Clean up label text
                        cleaned = label_text.strip().replace('*', '').replace(':', '').strip()
                        if cleaned:
                            return cleaned
            
            # Strategy 2: Check aria-label
            aria_label = await element.get_attribute('aria-label')
            if aria_label and aria_label.strip():
                return aria_label.strip()
            
            # Strategy 3: Check placeholder
            placeholder = await element.get_attribute('placeholder')
            if placeholder and placeholder.strip():
                return placeholder.strip()
        
        except Exception:
            pass
        
        return "Unlabeled Field"
    
    async def _extract_identifier(self, element) -> str:
        """Extract identifier with priority system"""
        try:
            # Priority 1: data-automation-id
            automation_id = await element.get_attribute('data-automation-id')
            if automation_id:
                return automation_id
            
            # Priority 2: id attribute
            element_id = await element.get_attribute('id')
            if element_id:
                return element_id
            
            # Priority 3: name attribute
            name_attr = await element.get_attribute('name')
            if name_attr:
                return name_attr
            
            # Priority 4: Check child elements
            child_input = await element.query_selector('input, select, textarea')
            if child_input:
                child_automation_id = await child_input.get_attribute('data-automation-id')
                if child_automation_id:
                    return child_automation_id
                
                child_id = await child_input.get_attribute('id')
                if child_id:
                    return child_id
                
                child_name = await child_input.get_attribute('name')
                if child_name:
                    return child_name
            
            # Priority 5: Generate from label
            label = await self._extract_label(element)
            if label and label != "Unlabeled Field":
                slug = ''.join(c if c.isalnum() else '_' for c in label.lower())
                return f"generated_{slug[:30]}"
        
        except Exception:
            pass
        
        return "no_identifier_found"
    
    async def _is_required(self, element) -> bool:
        """Detect required fields using multiple strategies"""
        try:
            # Strategy 1: Check element itself
            aria_required = await element.get_attribute('aria-required')
            if aria_required == 'true':
                return True
            
            required_attr = await element.get_attribute('required')
            if required_attr is not None:
                return True
            
            # Strategy 2: Check child elements
            child_inputs = await element.query_selector_all('input, select, textarea')
            for child_input in child_inputs:
                try:
                    child_aria_required = await child_input.get_attribute('aria-required')
                    if child_aria_required == 'true':
                        return True
                    
                    child_required = await child_input.get_attribute('required')
                    if child_required is not None:
                        return True
                except:
                    continue
            
            # Strategy 3: Check for required indicators
            if await element.query_selector('[aria-required="true"]'):
                return True
            
            if await element.query_selector('.WDSC-Required, .required'):
                return True
            
            # Strategy 4: Check for asterisk in label
            label_element = await element.query_selector('[data-automation-id="label"]')
            if label_element:
                label_text = await label_element.inner_text()
                if '*' in label_text:
                    return True
        
        except Exception:
            pass
        
        return False
    
    async def _extract_options(self, element, control_type: str) -> List[str]:
        """Extract options for multi-choice controls"""
        options = []
        
        try:
            if control_type in ("select", "multiselect"):
                # Handle dropdown options
                try:
                    # Try to click to open dropdown
                    await element.click()
                    await asyncio.sleep(0.5)
                    
                    # Look for options
                    option_elements = await element.query_selector_all('option, div[role="option"], li[role="option"]')
                    for opt in option_elements:
                        if await opt.is_visible():
                            option_text = await opt.inner_text()
                            if option_text.strip():
                                options.append(option_text.strip())
                    
                    # Close dropdown
                    await element.press("Escape")
                except:
                    # Fallback: look for option elements directly
                    option_elements = await element.query_selector_all('option')
                    for opt in option_elements:
                        option_text = await opt.inner_text()
                        if option_text.strip():
                            options.append(option_text.strip())
            
            elif control_type == "radio":
                # Handle radio button groups
                radio_elements = await element.query_selector_all('input[type="radio"]')
                for radio in radio_elements:
                    try:
                        radio_id = await radio.get_attribute('id')
                        if radio_id:
                            # Look for associated label
                            label = await element.query_selector(f'label[for="{radio_id}"]')
                            if label:
                                label_text = await label.inner_text()
                                if label_text.strip():
                                    options.append(label_text.strip())
                    except:
                        continue
            
            elif control_type == "checkbox":
                # Handle checkbox groups
                checkbox_elements = await element.query_selector_all('input[type="checkbox"]')
                for checkbox in checkbox_elements:
                    try:
                        checkbox_id = await checkbox.get_attribute('id')
                        if checkbox_id:
                            # Look for associated label
                            label = await element.query_selector(f'label[for="{checkbox_id}"]')
                            if label:
                                label_text = await label.inner_text()
                                if label_text.strip():
                                    options.append(label_text.strip())
                    except:
                        continue
        
        except Exception:
            pass
        
        return list(set(options))  # Remove duplicates
    
    def _generate_sample_values(self, control_type: str, options: List[str], label: str) -> List[str]:
        """Generate intelligent sample values"""
        if not options:
            return []
        
        label_lower = label.lower()
        
        if control_type in ("select", "radio"):
            # Smart selection based on question context
            
            # For visa/authorization questions, prefer "No"
            if any(keyword in label_lower for keyword in ['visa', 'sponsor', 'authorization']):
                for opt in options:
                    if opt.lower() in ['no', 'not required', 'none']:
                        return [opt]
            
            # For legal work authorization, prefer "Yes"
            if any(keyword in label_lower for keyword in ['legally authorized', 'authorized to work']):
                for opt in options:
                    if opt.lower() in ['yes', 'authorized', 'eligible']:
                        return [opt]
            
            # Default to first option
            return [options[0]]
        
        elif control_type in ("multiselect", "checkbox"):
            # For multi-select, typically choose first option
            return [options[0]]
        
        return []
    
    async def _create_results(self) -> ExtractionResults:
        """Create structured results"""
        # Convert form elements to dictionary format
        form_elements_dict = []
        for form_elem in self.form_elements:
            form_elements_dict.append({
                "label": form_elem.label,
                "id_of_input_component": form_elem.id_of_input_component,
                "required": form_elem.required,
                "type_of_input": form_elem.type_of_input,
                "options": form_elem.options,
                "user_data_select_values": form_elem.user_data_select_values
            })
        
        return ExtractionResults(
            form_elements=form_elements_dict,
            pages_visited=self.discovered_pages,
            total_pages_crawled=len(self.discovered_pages),
            total_form_elements=len(self.form_elements),
            extraction_timestamp=time.time(),
            tenant_url=self.tenant_url,
            errors=self.errors
        )
    
    async def _save_results(self, results: ExtractionResults):
        """Save results with metadata"""
        try:
            # Create comprehensive output
            output_data = {
                "extraction_metadata": {
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(results.extraction_timestamp)),
                    "tenant_url": results.tenant_url,
                    "total_pages_crawled": results.total_pages_crawled,
                    "total_form_elements": results.total_form_elements
                },
                "pages_visited": [
                    {
                        "url": page.url,
                        "title": page.title,
                        "page_type": page.page_type,
                        "form_count": page.form_count
                    }
                    for page in results.pages_visited
                ],
                "form_elements": results.form_elements,
                "errors": results.errors
            }
            
            # Save to file
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n💾 Results saved to: {OUTPUT_FILE}")
            
            # Print summary statistics
            self._print_summary(results)
            
        except Exception as e:
            print(f"❌ Error saving results: {str(e)}")
    
    def _print_summary(self, results: ExtractionResults):
        """Print extraction summary"""
        print(f"\n📊 Extraction Summary:")
        print(f"  Pages crawled: {results.total_pages_crawled}")
        print(f"  Form elements: {results.total_form_elements}")
        print(f"  Errors: {len(results.errors)}")
        
        if results.pages_visited:
            print(f"\n📄 Pages visited:")
            for page in results.pages_visited:
                print(f"    {page.page_type}: {page.title} ({page.form_count} forms)")
        
        # Element type breakdown
        if results.form_elements:
            element_types = {}
            for elem in results.form_elements:
                elem_type = elem['type_of_input']
                element_types[elem_type] = element_types.get(elem_type, 0) + 1
            
            print(f"\n🔧 Form element types:")
            for elem_type, count in sorted(element_types.items()):
                print(f"    {elem_type}: {count}")
        
        if results.errors:
            print(f"\n⚠️ Errors encountered:")
            for error in results.errors[:3]:  # Show first 3 errors
                print(f"    {error}")
            if len(results.errors) > 3:
                print(f"    ... and {len(results.errors) - 3} more errors")

async def main():
    """Main entry point"""
    try:
        scraper = WorkdayFormScraper()
        results = await scraper.run()
        
        # Print final status
        print(f"\n🎯 Final Status:")
        print(f"  Task completion: {'✅ Success' if results.total_form_elements > 0 else '❌ No forms found'}")
        print(f"  Form elements extracted: {results.total_form_elements}")
        
        return results
        
    except Exception as e:
        print(f"💥 Critical failure: {str(e)}")
        return None

if __name__ == "__main__":
    asyncio.run(main())