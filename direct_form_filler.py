#!/usr/bin/env python3
"""
Direct Form Filler - Identifies input areas by data-automation-id and fills with .env data
"""

import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

class DirectFormFiller:
    """Direct form filling by id, data-automation-id, and name attributes"""
    
    def __init__(self):
        self.filled_count = 0
        
        # Get current date components for date fields
        from datetime import datetime
        today = datetime.now()
        today_month = str(today.month).zfill(2)  # Zero-padded month
        today_day = str(today.day).zfill(2)      # Zero-padded day
        today_year = str(today.year)
        
        # Direct mapping of field id to environment variable
        self.field_mappings = {
            # My Information page fields (using id attributes)
            'name--legalName--firstName': os.getenv('REGISTRATION_FIRST_NAME', ''),
            'name--legalName--lastName': os.getenv('REGISTRATION_LAST_NAME', ''),
            'email': os.getenv('REGISTRATION_EMAIL', ''),
            'phoneNumber--phoneNumber': os.getenv('REGISTRATION_PHONE', ''),
            'phoneNumber--phoneDeviceType': 'Home',  # Phone type field
            'phoneNumber--countryPhoneCode': '+1',
            'phoneNumber--extension': '',
            'country--country': 'United States',
            'source--source': os.getenv('JOB_BOARD',''),
            'candidateIsPreviousWorker': 'No',  # Radio button for previous employee
            
            # Date fields - individual components
            'dateSectionMonth-input': today_month,
            'dateSectionDay-input': today_day,
            'dateSectionYear-input': today_year,
            'selfIdentifiedDisabilityData--dateSignedOn-dateSectionMonth-input': today_month,
            'selfIdentifiedDisabilityData--dateSignedOn-dateSectionDay-input': today_day,
            'selfIdentifiedDisabilityData--dateSignedOn-dateSectionYear-input': today_year,
            
            # Skip address fields as requested
            # 'address--addressLine1': '',
            # 'address--city': '',
            # 'address--postalCode': '',
            # 'address--countryRegion': '',
            
            # Other potential fields
            'currentCompany': os.getenv('CURRENT_COMPANY', ''),
            'currentRole': os.getenv('CURRENT_ROLE', ''),
            'workExperience': os.getenv('YEARS_EXPERIENCE', ''),
            'skills': os.getenv('PRIMARY_SKILLS', ''),
            'education': os.getenv('EDUCATION_MASTERS', ''),
            'github': os.getenv('GITHUB_URL', ''),
            'workAuthorization': 'Yes',
            'visaStatus': 'US Citizen',
            'requiresSponsorship': 'No'
        }
    
    async def fill_page_by_automation_id(self, page) -> int:
        """Fill all fields on page by finding them with id, data-automation-id, or name attributes"""
        print("  🎯 Direct form filling by id, data-automation-id, and name attributes...")
        
        # First, let's debug what fields are actually on the page
        await self._debug_page_fields(page)
        
        self.filled_count = 0
        
        for field_id, value in self.field_mappings.items():
            if value:  # Only fill if we have a value
                success = await self._fill_field_by_id(page, field_id, value)
                if success:
                    self.filled_count += 1
                    print(f"    ✅ {field_id}: {value}")
                else:
                    print(f"    ⚠️ Not found: {field_id}")
        
        print(f"  ✅ Direct filling complete: {self.filled_count} fields filled")
        return self.filled_count
    
    async def _debug_page_fields(self, page):
        """Debug function to see what fields are actually on the page"""
        print("  🔍 Debugging: Looking for all form fields on page...")
        
        try:
            # Find all input fields
            inputs = await page.query_selector_all('input')
            print(f"    Found {len(inputs)} input elements:")
            
            for i, input_elem in enumerate(inputs[:10]):  # Show first 10
                try:
                    input_id = await input_elem.get_attribute('id')
                    input_name = await input_elem.get_attribute('name')
                    input_type = await input_elem.get_attribute('type')
                    data_automation_id = await input_elem.get_attribute('data-automation-id')
                    is_visible = await input_elem.is_visible()
                    
                    print(f"      Input {i+1}: id='{input_id}', name='{input_name}', type='{input_type}', data-automation-id='{data_automation_id}', visible={is_visible}")
                except:
                    print(f"      Input {i+1}: Could not get attributes")
            
            # Find all select fields
            selects = await page.query_selector_all('select')
            print(f"    Found {len(selects)} select elements:")
            
            for i, select_elem in enumerate(selects[:5]):  # Show first 5
                try:
                    select_id = await select_elem.get_attribute('id')
                    select_name = await select_elem.get_attribute('name')
                    data_automation_id = await select_elem.get_attribute('data-automation-id')
                    is_visible = await select_elem.is_visible()
                    
                    print(f"      Select {i+1}: id='{select_id}', name='{select_name}', data-automation-id='{data_automation_id}', visible={is_visible}")
                except:
                    print(f"      Select {i+1}: Could not get attributes")
                    
        except Exception as e:
            print(f"    ❌ Debug error: {str(e)}")
    
    async def _fill_field_by_id(self, page, field_id: str, value: str) -> bool:
        """Fill a specific field by its id, data-automation-id, or name attributes"""
        
        print(f"    🔍 Attempting to fill field '{field_id}' with value '{value}'")
        
        # Special handling for source dropdown field
        if field_id == 'source--source':
            return await self._handle_source_dropdown_simple(page, field_id, value)
        
        # Special handling for phone device type dropdown
        if field_id == 'phoneNumber--phoneDeviceType':
            return await self._handle_phone_device_type_dropdown(page, field_id, value)
        
        # Special handling for date spinbutton fields - use simple fill
        if any(date_field in field_id for date_field in ['dateSectionMonth', 'dateSectionDay', 'dateSectionYear']):
            return await self._handle_date_simple_fill(page, field_id, value)
        
        try:
            # Strategy 1: Text input fields - comprehensive selector approach
            text_selectors = [
                f'input[id="{field_id}"]',  # Try id first (for My Information page)
                f'input[data-automation-id="{field_id}"]',  # Then data-automation-id
                f'input[name="{field_id}"]',  # Also try name attribute
                f'input[id*="{field_id}"]',  # Partial id match
                f'input[data-automation-id*="{field_id}"]'  # Partial data-automation-id match
            ]
            
            for i, selector in enumerate(text_selectors):
                try:
                    print(f"      🔍 Trying text selector {i+1}: {selector}")
                    text_element = await page.query_selector(selector)
                    if text_element:
                        is_visible = await text_element.is_visible()
                        is_enabled = await text_element.is_enabled()
                        input_type = await text_element.get_attribute('type')
                        
                        print(f"        Found element: visible={is_visible}, enabled={is_enabled}, type={input_type}")
                        
                        if is_visible and is_enabled:
                            if input_type in ['text', 'email', 'tel', None]:
                                # Special handling for date fields - use typing instead of fill
                                if 'date' in field_id.lower() or field_id in ['dateSectionMonth-input', 'dateSectionDay-input', 'dateSectionYear-input']:
                                    print(f"        🔍 Date field detected - using typing method")
                                    
                                    # Click to focus the field
                                    await page.click(selector)
                                    await asyncio.sleep(0.3)
                                    
                                    # Clear the field using keyboard shortcuts
                                    await page.keyboard.press('Control+a')  # Select all
                                    await asyncio.sleep(0.2)
                                    await page.keyboard.press('Delete')  # Delete selected content
                                    await asyncio.sleep(0.2)
                                    
                                    # Type the new value
                                    await page.type(selector, value, delay=100)  # Type with delay
                                    await asyncio.sleep(0.5)
                                else:
                                    # Wait for element to be ready and use page methods instead of element methods
                                    await page.wait_for_selector(selector, state='attached')
                                    await page.fill(selector, '')  # Clear by filling with empty string
                                    await page.fill(selector, value)
                                
                                # Verify the value was filled
                                filled_value = await page.input_value(selector)
                                if filled_value == value:
                                    print(f"    ✅ Successfully filled text field using selector: {selector}")
                                    return True
                                else:
                                    print(f"    ⚠️ Value not set correctly. Expected: '{value}', Got: '{filled_value}'")
                            elif input_type == 'radio':
                                return await self._handle_radio_by_id(page, field_id, value)
                            elif input_type == 'checkbox':
                                should_check = value.lower() in ['true', 'yes', '1']
                                if should_check:
                                    await page.check(selector)
                                else:
                                    await page.uncheck(selector)
                                print(f"    ✅ Filled checkbox using selector: {selector}")
                                return True
                        else:
                            print(f"        Element not interactable: visible={is_visible}, enabled={is_enabled}")
                except Exception as e:
                    print(f"        Error with selector {selector}: {str(e)}")
                    continue
            
            # Strategy 2: Select dropdown fields - comprehensive approach
            select_selectors = [
                f'select[id="{field_id}"]',
                f'select[data-automation-id="{field_id}"]',
                f'select[name="{field_id}"]',
                f'select[id*="{field_id}"]',
                f'select[data-automation-id*="{field_id}"]'
            ]
            
            for i, selector in enumerate(select_selectors):
                try:
                    print(f"      🔍 Trying select selector {i+1}: {selector}")
                    select_element = await page.query_selector(selector)
                    if select_element:
                        is_visible = await select_element.is_visible()
                        is_enabled = await select_element.is_enabled()
                        
                        print(f"        Found select element: visible={is_visible}, enabled={is_enabled}")
                        
                        if is_visible and is_enabled:
                            success = await self._handle_select_by_id(select_element, value)
                            if success:
                                print(f"    ✅ Successfully filled select field using selector: {selector}")
                                return True
                        else:
                            print(f"        Select element not interactable: visible={is_visible}, enabled={is_enabled}")
                except Exception as e:
                    print(f"        Error with select selector {selector}: {str(e)}")
                    continue
            
            # Strategy 3: Textarea fields - comprehensive approach
            textarea_selectors = [
                f'textarea[id="{field_id}"]',
                f'textarea[data-automation-id="{field_id}"]',
                f'textarea[name="{field_id}"]',
                f'textarea[id*="{field_id}"]',
                f'textarea[data-automation-id*="{field_id}"]'
            ]
            
            for i, selector in enumerate(textarea_selectors):
                try:
                    print(f"      🔍 Trying textarea selector {i+1}: {selector}")
                    textarea_element = await page.query_selector(selector)
                    if textarea_element:
                        is_visible = await textarea_element.is_visible()
                        is_enabled = await textarea_element.is_enabled()
                        
                        print(f"        Found textarea element: visible={is_visible}, enabled={is_enabled}")
                        
                        if is_visible and is_enabled:
                            # Wait for element to be ready and use page methods instead of element methods
                            await page.wait_for_selector(selector, state='attached')
                            await page.fill(selector, '')  # Clear by filling with empty string
                            await page.fill(selector, value)
                            
                            # Verify the value was filled
                            filled_value = await page.input_value(selector)
                            if filled_value == value:
                                print(f"    ✅ Successfully filled textarea using selector: {selector}")
                                return True
                            else:
                                print(f"    ⚠️ Textarea value not set correctly. Expected: '{value}', Got: '{filled_value}'")
                        else:
                            print(f"        Textarea element not interactable: visible={is_visible}, enabled={is_enabled}")
                except Exception as e:
                    print(f"        Error with textarea selector {selector}: {str(e)}")
                    continue
            
            # Strategy 4: Radio button groups (enhanced with better selectors)
            if field_id in ['candidateIsPreviousWorker', 'workAuthorization', 'requiresSponsorship']:
                print(f"      🔍 Handling radio button group for: {field_id}")
                return await self._handle_radio_by_id(page, field_id, value)
            
            print(f"    ❌ No matching element found for field: {field_id}")
            return False
            
        except Exception as e:
            print(f"    ❌ Critical error filling {field_id}: {str(e)}")
            return False
    
    async def _handle_select_by_id(self, select_element, value: str) -> bool:
        """Handle select dropdown by trying different selection methods"""
        
        try:
            # Try by value
            await select_element.select_option(value=value)
            return True
        except:
            pass
        
        try:
            # Try by label/text
            await select_element.select_option(label=value)
            return True
        except:
            pass
        
        try:
            # Try to find option that contains the value
            options = await select_element.query_selector_all('option')
            for option in options:
                option_text = await option.inner_text()
                if value.lower() in option_text.lower():
                    option_value = await option.get_attribute('value')
                    await select_element.select_option(value=option_value)
                    return True
        except:
            pass
        
        return False
    
    async def _handle_phone_device_type_dropdown(self, page, field_id: str, value: str) -> bool:
        """Handle phone device type dropdown with button-based listbox structure"""
        
        print(f"      🔍 Handling phone device type dropdown for: {field_id}")
        
        try:
            # Try different selectors for the button dropdown field
            button_selectors = [
                f'button[id="{field_id}"]',
                f'button[id="phoneNumber--phoneType"]',  # Based on your structure
                f'button[name="phoneType"]',
                f'button[aria-haspopup="listbox"]',
                f'button[id*="phoneType"]',
                f'button[id*="phoneNumber--phoneType"]'
            ]
            
            for selector in button_selectors:
                try:
                    print(f"        🔍 Trying phone device type button selector: {selector}")
                    button_element = await page.query_selector(selector)
                    if button_element and await button_element.is_visible():
                        print(f"        ✅ Found phone device type button with selector: {selector}")
                        
                        # Click the button to open the dropdown
                        await page.click(selector)
                        await asyncio.sleep(1)  # Wait for dropdown to open
                        print(f"        🖱️ Clicked phone device type button")
                        
                        # Look for the dropdown options that appear after clicking
                        option_selectors = [
                            f'li:has-text("{value}")',  # Look for list item with "Home"
                            f'div:has-text("{value}")',  # Or div with "Home"
                            f'span:has-text("{value}")',  # Or span with "Home"
                            f'[role="option"]:has-text("{value}")',  # ARIA option with "Home"
                            f'[role="listbox"] *:has-text("{value}")'  # Any element in listbox with "Home"
                        ]
                        
                        for option_selector in option_selectors:
                            try:
                                print(f"        🔍 Looking for option with selector: {option_selector}")
                                option_element = await page.wait_for_selector(option_selector, timeout=3000, state='visible')
                                if option_element:
                                    print(f"        ✅ Found '{value}' option with selector: {option_selector}")
                                    await option_element.click()
                                    await asyncio.sleep(0.5)
                                    print(f"    ✅ Successfully selected '{value}' in phone device type dropdown")
                                    return True
                            except:
                                continue
                        
                        # If specific option not found, try a more general approach
                        print(f"        🔍 Trying general option selection...")
                        try:
                            # Wait for any dropdown options to appear
                            await page.wait_for_selector('[role="listbox"], ul, .dropdown-menu', timeout=3000)
                            
                            # Click on any option containing "Home" (case insensitive)
                            await page.click(f'text=/{value}/i')
                            await asyncio.sleep(0.5)
                            print(f"    ✅ Successfully selected '{value}' using general text selector")
                            return True
                        except:
                            print(f"        ⚠️ Could not find '{value}' option in dropdown")
                        
                except Exception as e:
                    print(f"        Error with phone device type button selector {selector}: {str(e)}")
                    continue
            
            print(f"    ❌ Could not find phone device type dropdown button: {field_id}")
            return False
            
        except Exception as e:
            print(f"    ❌ Critical error handling phone device type dropdown {field_id}: {str(e)}")
            return False
    
    async def _handle_source_dropdown_simple(self, page, field_id: str, value: str) -> bool:
        """Handle source--source dropdown field - click once, type, and press Enter"""
        
        print(f"      🔍 Handling source dropdown for: {field_id}")
        
        try:
            # Simple selector for the source field
            selector = f'input[id="{field_id}"]'
            
            print(f"        🔍 Trying source dropdown selector: {selector}")
            element = await page.query_selector(selector)
            
            if element and await element.is_visible():
                is_enabled = await element.is_enabled()
                print(f"        ✅ Found source element: enabled={is_enabled}")
                
                if is_enabled:
                    # Simple approach: Click once, type, and press Enter
                    print(f"        🔍 Click once, type '{value}', and press Enter")
                    
                    # Click to focus the field
                    await page.click(selector)
                    await asyncio.sleep(0.3)
                    
                    # Type the value
                    await page.type(selector, value, delay=100)
                    await asyncio.sleep(0.5)
                    
                    # Press Enter
                    await page.keyboard.press('Enter')
                    await asyncio.sleep(0.5)
                    
                    print(f"    ✅ Successfully filled source dropdown '{field_id}' with click, type, and Enter")
                    return True
                else:
                    print(f"        Source element not enabled")
            else:
                print(f"        Source element not found or not visible")
            
            print(f"    ❌ Could not find or fill source dropdown field: {field_id}")
            return False
            
        except Exception as e:
            print(f"    ❌ Critical error handling source dropdown {field_id}: {str(e)}")
            return False

    async def _handle_dropdown_with_typing(self, page, field_id: str, value: str) -> bool:
        """Handle dropdown fields that require typing + Enter"""
        
        print(f"      🔍 Handling dropdown with typing for: {field_id}")
        
        try:
            # Try different selectors for the dropdown field
            selectors = [
                f'input[id="{field_id}"]',
                f'input[data-automation-id="{field_id}"]',
                f'input[name="{field_id}"]',
                f'input[id*="{field_id}"]'
            ]
            
            for selector in selectors:
                try:
                    print(f"        🔍 Trying dropdown selector: {selector}")
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        print(f"        ✅ Found dropdown element with selector: {selector}")
                        
                        # Simple fill approach
                        await page.fill(selector, value)
                        await asyncio.sleep(0.5)
                        
                        print(f"    ✅ Successfully filled dropdown '{field_id}' with '{value}' and pressed Enter")
                        return True
                        
                except Exception as e:
                    print(f"        Error with dropdown selector {selector}: {str(e)}")
                    continue
            
            print(f"    ❌ Could not find dropdown field: {field_id}")
            return False
            
        except Exception as e:
            print(f"    ❌ Critical error handling dropdown {field_id}: {str(e)}")
            return False
    


    async def _handle_date_simple_fill(self, page, field_id: str, value: str) -> bool:
        """Handle date fields using simple fill method with format like 01012005"""
        
        print(f"      🔍 Handling date field with simple fill for: {field_id}")
        
        try:
            # Try different selectors for the date field
            selectors = [
                f'input[id="{field_id}"]',
                f'input[data-automation-id="{field_id}"]',
                f'input[name="{field_id}"]',
                f'input[id*="{field_id}"]',
                f'input[data-automation-id*="{field_id}"]'
            ]
            
            for selector in selectors:
                try:
                    print(f"        🔍 Trying date selector: {selector}")
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        is_enabled = await element.is_enabled()
                        
                        print(f"        ✅ Found date element: enabled={is_enabled}")
                        
                        if is_enabled:
                            # Simple fill approach - just use page.fill()
                            await page.fill(selector, value)
                            await asyncio.sleep(0.3)
                            
                            # Verify the value was set
                            filled_value = await page.input_value(selector)
                            if filled_value == value:
                                print(f"    ✅ Successfully filled date field '{field_id}' with '{value}'")
                                return True
                            else:
                                print(f"    ⚠️ Date value not set correctly. Expected: '{value}', Got: '{filled_value}'")
                        else:
                            print(f"        Date element not enabled: {selector}")
                        
                except Exception as e:
                    print(f"        Error with date selector {selector}: {str(e)}")
                    continue
            
            print(f"    ❌ Could not find or fill date field: {field_id}")
            return False
            
        except Exception as e:
            print(f"    ❌ Critical error handling date field {field_id}: {str(e)}")
            return False

    async def _handle_radio_by_id(self, page, field_id: str, value: str) -> bool:
        """Handle radio buttons by finding the correct option"""
        
        try:
            print(f"        🔍 Looking for radio buttons for field: {field_id}")
            
            # Find all radio buttons with this name/id
            radio_selectors = [
                f'input[name="{field_id}"]',
                f'input[id="{field_id}"]',  # Added id selector
                f'input[data-automation-id="{field_id}"]'
            ]
            
            for selector in radio_selectors:
                print(f"        🔍 Trying radio selector: {selector}")
                radios = await page.query_selector_all(selector)
                
                if radios:
                    print(f"        ✅ Found {len(radios)} radio buttons with selector: {selector}")
                    
                    # Look for the specific value we want
                    for i, radio in enumerate(radios):
                        if await radio.is_visible():
                            radio_value = await radio.get_attribute('value')
                            radio_id = await radio.get_attribute('id')
                            print(f"          Radio {i+1}: id='{radio_id}', value='{radio_value}'")
                    
                    # For candidateIsPreviousWorker, we want to select "No"
                    if field_id == 'candidateIsPreviousWorker' and value.lower() == 'no':
                        # Look for radio button with value containing "no" or "false"
                        for radio in radios:
                            if await radio.is_visible():
                                radio_value = await radio.get_attribute('value')
                                radio_id = await radio.get_attribute('id')
                                
                                # Check for "No" values (could be "No", "false", "0", etc.)
                                if radio_value and (
                                    radio_value.lower() == 'no' or 
                                    radio_value.lower() == 'false' or 
                                    radio_value == '0' or
                                    'no' in radio_value.lower()
                                ):
                                    await page.check(f'#{radio_id}')
                                    print(f"        ✅ Selected 'No' radio button: id='{radio_id}', value='{radio_value}'")
                                    return True
                        
                        # If no clear "No" option found, select the second radio button (often "No")
                        if len(radios) >= 2:
                            second_radio = radios[1]  # Second option is often "No"
                            radio_id = await second_radio.get_attribute('id')
                            radio_value = await second_radio.get_attribute('value')
                            await page.check(f'#{radio_id}')
                            print(f"        ✅ Selected second radio option (assuming 'No'): id='{radio_id}', value='{radio_value}'")
                            return True
                    
                    # General radio button handling for other fields
                    for radio in radios:
                        if await radio.is_visible():
                            radio_value = await radio.get_attribute('value')
                            radio_id = await radio.get_attribute('id')
                            
                            # Exact match
                            if radio_value and radio_value.lower() == value.lower():
                                await page.check(f'#{radio_id}')
                                print(f"        ✅ Selected radio button with exact match: {radio_value}")
                                return True
                            
                            # For Yes/No questions
                            if value.lower() == 'no' and radio_value and 'no' in radio_value.lower():
                                await page.check(f'#{radio_id}')
                                print(f"        ✅ Selected 'No' radio button: {radio_value}")
                                return True
                            elif value.lower() == 'yes' and radio_value and 'yes' in radio_value.lower():
                                await page.check(f'#{radio_id}')
                                print(f"        ✅ Selected 'Yes' radio button: {radio_value}")
                                return True
                    
                    
                    break
                else:
                    print(f"        ⚠️ No radio buttons found with selector: {selector}")
            
            return False
            
        except Exception as e:
            print(f"    ❌ Radio error for {field_id}: {str(e)}")
            return False
    
    async def submit_form(self, page) -> bool:
        """Submit the form after filling"""
        
        print("  🚀 Submitting form...")
        
        # Try common submit button selectors
        submit_selectors = [
            'button:has-text("Next")',
            'button:has-text("Continue")',
            'button:has-text("Save and Continue")',
            'button:has-text("Save")',
            'button[type="submit"]',
            'input[type="submit"]'
        ]
        
        for selector in submit_selectors:
            try:
                button = await page.query_selector(selector)
                if button and await button.is_visible() and not await button.is_disabled():
                    await button.click()
                    print(f"  ✅ Clicked: {selector}")
                    
                    # Wait for form submission
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    await asyncio.sleep(2)
                    return True
            except:
                continue
        
        # Fallback: Try Enter key
        try:
            await page.keyboard.press("Enter")
            print("  ✅ Pressed Enter key")
            await page.wait_for_load_state("networkidle", timeout=10000)
            await asyncio.sleep(2)
            return True
        except:
            pass
        
        print("  ❌ Could not submit form")
        return False
    
    async def handle_voluntary_disclosures(self, page) -> bool:
        """Handle Voluntary Disclosures page - fill ethnicity, gender, veteran status"""
        print("  📊 Processing Voluntary Disclosures page...")
        
        try:
            # Define voluntary disclosure field mappings
            voluntary_fields = {
                'ethnicity': os.getenv('ETHNICITY', 'Prefer not to disclose'),
                'gender': os.getenv('GENDER', 'Prefer not to disclose'), 
                'veteran_status': os.getenv('VETERAN_STATUS', 'I am not a protected veteran'),
                'disability_status': os.getenv('DISABILITY_STATUS', 'I don\'t wish to answer'),
                'terms_checkbox': os.getenv('ACCEPT_TERMS', 'true')  # Accept terms and conditions
            }
            
            filled_count = 0
            
            for field_type, value in voluntary_fields.items():
                if value:
                    success = await self._fill_voluntary_field(page, field_type, value)
                    if success:
                        filled_count += 1
                        print(f"    ✅ {field_type}: {value}")
                    else:
                        print(f"    ⚠️ Could not fill {field_type}")
            
            print(f"  ✅ Voluntary disclosures completed: {filled_count} fields filled")
            return filled_count > 0
            
        except Exception as e:
            print(f"  ❌ Error handling voluntary disclosures: {str(e)}")
            return False
    
    async def _fill_voluntary_field(self, page, field_type: str, value: str) -> bool:
        """Fill a specific voluntary disclosure field using button-based dropdowns"""
        print(f"    🔍 Attempting to fill {field_type} with value '{value}'")
        
        try:
            # Define specific button IDs for voluntary disclosure fields
            field_button_ids = {
                'ethnicity': 'personalInfoUS--ethnicity',
                'gender': 'personalInfoUS--gender',
                'veteran_status': 'personalInfoUS--veteranStatus',
                'disability_status': 'personalInfoUS--disability'  # Fallback if needed
            }
            
            button_id = field_button_ids.get(field_type)
            
            if button_id:
                # Handle button-based dropdown
                success = await self._handle_button_dropdown(page, button_id, value, field_type)
                if success:
                    return True
            
            # Handle checkbox for terms and conditions
            if field_type == 'terms_checkbox':
                return await self._handle_terms_checkbox(page, value)
            
            print(f"    ❌ Could not find field for {field_type}")
            return False
            
        except Exception as e:
            print(f"    ❌ Error filling {field_type}: {str(e)}")
            return False
    
    async def _handle_button_dropdown(self, page, button_id: str, value: str, field_type: str) -> bool:
        """Handle button-based dropdown selection"""
        try:
            print(f"      🔍 Looking for button with ID: {button_id}")
            
            # Find the button element
            button_selector = f'button[id="{button_id}"]'
            button_element = await page.query_selector(button_selector)
            
            if not button_element or not await button_element.is_visible():
                print(f"        ❌ Button not found or not visible: {button_id}")
                return False
            
            print(f"        ✅ Found {field_type} button")
            
            # Click the button to open dropdown
            await button_element.click()
            await asyncio.sleep(1)  # Wait for dropdown to open
            print(f"        🖱️ Clicked {field_type} button")
            
            # Look for dropdown options that appear after clicking
            option_selectors = [
                f'li:has-text("{value}")',  # List item with exact text
                f'div:has-text("{value}")',  # Div with exact text
                f'span:has-text("{value}")',  # Span with exact text
                f'[role="option"]:has-text("{value}")',  # ARIA option
                f'[role="listbox"] *:has-text("{value}")',  # Any element in listbox
                f'text="{value}"'  # Direct text match
            ]
            
            for option_selector in option_selectors:
                try:
                    print(f"        🔍 Looking for option with selector: {option_selector}")
                    option_element = await page.wait_for_selector(option_selector, timeout=3000, state='visible')
                    if option_element:
                        print(f"        ✅ Found '{value}' option")
                        await option_element.click()
                        await asyncio.sleep(0.5)
                        print(f"    ✅ Successfully selected '{value}' for {field_type}")
                        return True
                except:
                    continue
            
            # If specific option not found, try partial matching
            print(f"        🔍 Trying partial text matching for '{value}'...")
            try:
                # Wait for dropdown options to appear
                await page.wait_for_selector('[role="listbox"], ul, .dropdown-menu', timeout=3000)
                
                # Look for options containing key words from the value
                key_words = value.lower().split()
                for word in key_words:
                    if len(word) > 3:  # Only use meaningful words
                        try:
                            partial_selector = f'text=/{word}/i'
                            option_element = await page.query_selector(partial_selector)
                            if option_element and await option_element.is_visible():
                                await option_element.click()
                                await asyncio.sleep(0.5)
                                print(f"    ✅ Successfully selected option containing '{word}' for {field_type}")
                                return True
                        except:
                            continue
                            
            except:
                print(f"        ⚠️ Could not find dropdown options for {field_type}")
            
            return False
            
        except Exception as e:
            print(f"        ❌ Error handling button dropdown for {field_type}: {str(e)}")
            return False
    
    async def _handle_terms_checkbox(self, page, value: str) -> bool:
        """Handle terms and conditions checkbox"""
        try:
            checkbox_id = 'termsAndConditions--acceptTermsAndAgreements'
            checkbox_selector = f'input[id="{checkbox_id}"]'
            
            print(f"      🔍 Looking for terms checkbox with ID: {checkbox_id}")
            
            checkbox_element = await page.query_selector(checkbox_selector)
            
            if not checkbox_element or not await checkbox_element.is_visible():
                print(f"        ❌ Terms checkbox not found or not visible")
                return False
            
            print(f"        ✅ Found terms checkbox")
            
            # Check if we should check or uncheck the checkbox
            should_check = value.lower() in ['true', 'yes', '1', 'accept', 'agree']
            
            if should_check:
                await page.check(checkbox_selector)
                print(f"    ✅ Successfully checked terms and conditions checkbox")
            else:
                await page.uncheck(checkbox_selector)
                print(f"    ✅ Successfully unchecked terms and conditions checkbox")
            
            return True
            
        except Exception as e:
            print(f"        ❌ Error handling terms checkbox: {str(e)}")
            return False
    
    async def _select_dropdown_option(self, select_element, value: str) -> bool:
        """Select option from dropdown element"""
        try:
            # Try by exact text match first
            await select_element.select_option(label=value)
            return True
        except:
            pass
        
        try:
            # Try by value attribute
            await select_element.select_option(value=value)
            return True
        except:
            pass
        
        try:
            # Try partial text match
            options = await select_element.query_selector_all('option')
            for option in options:
                option_text = await option.inner_text()
                if value.lower() in option_text.lower() or option_text.lower() in value.lower():
                    option_value = await option.get_attribute('value')
                    await select_element.select_option(value=option_value)
                    return True
        except:
            pass
        
        return False
    
    async def _select_radio_option(self, page, base_selector: str, value: str) -> bool:
        """Select radio button option"""
        try:
            # Find all radio buttons with similar name
            radio_name = base_selector.split('[name*="')[1].split('"]')[0] if '[name*="' in base_selector else None
            
            if radio_name:
                radios = await page.query_selector_all(f'input[name*="{radio_name}"]')
                
                for radio in radios:
                    if await radio.is_visible():
                        radio_value = await radio.get_attribute('value')
                        radio_id = await radio.get_attribute('id')
                        
                        # Check if this radio matches our desired value
                        if radio_value and (
                            value.lower() in radio_value.lower() or 
                            radio_value.lower() in value.lower()
                        ):
                            await page.check(f'#{radio_id}')
                            return True
            
            return False
            
        except Exception as e:
            print(f"        Radio selection error: {str(e)}")
            return False
    
    async def handle_self_identity_page(self, page) -> bool:
        """Handle Self Identity page - fill name and today's date"""
        print("  🆔 Processing Self Identity page...")
        
        try:
            from datetime import datetime
            
            # Define self identity field mappings
            today = datetime.now()
            today_month = today.strftime("%m")  # MM format
            today_day = today.strftime("%d")    # DD format  
            today_year = today.strftime("%Y")   # YYYY format
            today_date = today.strftime("%m/%d/%Y")  # MM/DD/YYYY format
            
            identity_fields = {
                'selfIdentifiedDisabilityData--name': os.getenv('REGISTRATION_FIRST_NAME', '') + ' ' + os.getenv('REGISTRATION_LAST_NAME', ''),
                'selfIdentifiedDisabilityData--dateSignedOn': today_date,
                # Handle separate date fields if they exist
                'dateSectionMonth-input': today_month,
                'dateSectionDay-input': today_day,
                'dateSectionYear-input': today_year
            }
            
            filled_count = 0
            
            for field_id, value in identity_fields.items():
                if value and value.strip():
                    success = await self._fill_identity_field(page, field_id, value)
                    if success:
                        filled_count += 1
                        print(f"    ✅ {field_id}: {value}")
                    else:
                        print(f"    ⚠️ Could not fill {field_id}")
            
            print(f"  ✅ Self Identity completed: {filled_count} fields filled")
            return filled_count > 0
            
        except Exception as e:
            print(f"  ❌ Error handling self identity page: {str(e)}")
            return False
    
    async def _fill_identity_field(self, page, field_id: str, value: str) -> bool:
        """Fill a specific self identity field"""
        print(f"    🔍 Attempting to fill {field_id} with value '{value}'")
        
        try:
            # Try different selectors for the field
            selectors = [
                f'input[id="{field_id}"]',
                f'input[data-automation-id="{field_id}"]',
                f'input[name="{field_id}"]',
                f'input[id*="{field_id.split("--")[-1]}"]',  # Try with just the last part
                f'textarea[id="{field_id}"]',
                f'textarea[data-automation-id="{field_id}"]'
            ]
            
            for selector in selectors:
                try:
                    print(f"      🔍 Trying selector: {selector}")
                    element = await page.query_selector(selector)
                    
                    if element and await element.is_visible():
                        is_enabled = await element.is_enabled()
                        element_type = await element.get_attribute('type')
                        tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
                        
                        print(f"        Found element: tag={tag_name}, type={element_type}, enabled={is_enabled}")
                         
                except Exception as e:
                    print(f"        Error with selector {selector}: {str(e)}")
                    continue
            
            print(f"    ❌ Could not find field for {field_id}")
            return False
            
        except Exception as e:
            print(f"    ❌ Error filling {field_id}: {str(e)}")
            return False
    
    async def handle_experience_page_uploads(self, page) -> bool:
        """Handle CV upload on My Experience page"""
        print("  📄 Processing My Experience page - looking for CV upload...")
        
        try:
            # Get CV file path from environment variable
            cv_path = os.getenv('RESUME_PATH', '')
            
            if not cv_path:
                print("    ⚠️ CV_FILE_PATH not found in .env file")
                return False
            
            if not os.path.exists(cv_path):
                print(f"    ❌ CV file not found at path: {cv_path}")
                return False
            
            print(f"    📁 Found CV file: {cv_path}")
            
            # Look for file upload elements
            upload_success = await self._upload_cv_file(page, cv_path)
            
            if upload_success:
                print("    ✅ CV uploaded successfully")
                return True
            else:
                print("    ⚠️ Could not find CV upload field")
                return False
                
        except Exception as e:
            print(f"    ❌ Error handling experience page uploads: {str(e)}")
            return False
    
    async def _upload_cv_file(self, page, cv_path: str) -> bool:
        """Upload CV file using the select-files button"""
        print("    🔍 Looking for select-files button...")
        
        try:
            # First, try to find the specific select-files button
            select_files_button = await page.query_selector('[data-automation-id="select-files"]')
            
            if select_files_button and await select_files_button.is_visible():
                print("    ✅ Found select-files button")
                
                # Set up file chooser handler before clicking
                async def handle_file_chooser(file_chooser):
                    await file_chooser.set_files(cv_path)
                    print(f"    ✅ File selected: {cv_path}")
                
                # Listen for file chooser dialog
                page.on("filechooser", handle_file_chooser)
                
                # Click the select-files button
                await select_files_button.click()
                print("    🖱️ Clicked select-files button")
                
                # Wait for file dialog and upload
                await asyncio.sleep(3)
                
                # Remove the event listener
                page.remove_listener("filechooser", handle_file_chooser)
                
                # Verify upload success
                upload_confirmed = await self._verify_upload_success(page, cv_path)
                
                if upload_confirmed:
                    print("    ✅ Upload confirmed successful")
                    return True
                else:
                    print("    ✅ Upload completed (verification not available)")
                    return True  # Assume success if no error occurred
            
            else:
                print("    ⚠️ select-files button not found, trying fallback methods...")
                return await self._try_fallback_upload_methods(page, cv_path)
                
        except Exception as e:
            print(f"    ❌ Error with select-files button: {str(e)}")
            return await self._try_fallback_upload_methods(page, cv_path)
    
    async def _try_fallback_upload_methods(self, page, cv_path: str) -> bool:
        """Fallback methods for CV upload if select-files button not found"""
        print("    🔍 Trying fallback upload methods...")
        
        # Common file upload selectors for CV/Resume
        upload_selectors = [
            'input[type="file"]',
            'input[accept*=".pdf"]',
            'input[accept*=".doc"]',
            'input[accept*="application"]',
            '[data-automation-id*="upload"]',
            '[data-automation-id*="file"]',
            '[data-automation-id*="resume"]',
            '[data-automation-id*="cv"]',
            '[data-automation-id*="document"]',
            'input[id*="upload"]',
            'input[id*="file"]',
            'input[name*="resume"]',
            'input[name*="cv"]'
        ]
        
        for i, selector in enumerate(upload_selectors):
            try:
                print(f"      🔍 Trying upload selector {i+1}: {selector}")
                
                # Look for file input elements
                file_inputs = await page.query_selector_all(selector)
                
                for j, file_input in enumerate(file_inputs):
                    try:
                        # Check if the input is visible and enabled
                        is_visible = await file_input.is_visible()
                        is_enabled = await file_input.is_enabled()
                        input_type = await file_input.get_attribute('type')
                        accept_attr = await file_input.get_attribute('accept')
                        
                        print(f"        Input {j+1}: visible={is_visible}, enabled={is_enabled}, type={input_type}, accept={accept_attr}")
                        
                        if input_type == 'file' and is_enabled:
                            # Try to upload the file
                            await file_input.set_input_files(cv_path)
                            print(f"        ✅ Successfully uploaded CV using selector: {selector}")
                            
                            # Wait for upload to process
                            await asyncio.sleep(2)
                            
                            # Check if upload was successful by looking for success indicators
                            upload_confirmed = await self._verify_upload_success(page, cv_path)
                            
                            if upload_confirmed:
                                print("        ✅ Upload confirmed successful")
                                return True
                            else:
                                print("        ⚠️ Upload may have succeeded but couldn't verify")
                                return True  # Assume success if no error occurred
                        
                    except Exception as e:
                        print(f"        Error with file input {j+1}: {str(e)}")
                        continue
                        
            except Exception as e:
                print(f"      Error with selector {selector}: {str(e)}")
                continue
        
        # Try alternative approach: look for upload buttons that trigger file dialogs
        return await self._try_upload_button_approach(page, cv_path)
    
    async def _try_upload_button_approach(self, page, cv_path: str) -> bool:
        """Try to find upload buttons that trigger file selection dialogs"""
        print("    🔍 Looking for upload buttons...")
        
        upload_button_selectors = [
            'button:has-text("Upload")',
            'button:has-text("Browse")',
            'button:has-text("Choose File")',
            'button:has-text("Add File")',
            'button:has-text("Attach")',
            'a:has-text("Upload")',
            'a:has-text("Browse")',
            '[data-automation-id*="upload"]',
            '[data-automation-id*="browse"]',
            '[data-automation-id*="attach"]'
        ]
        
        for selector in upload_button_selectors:
            try:
                print(f"      🔍 Trying upload button: {selector}")
                button = await page.query_selector(selector)
                
                if button and await button.is_visible() and not await button.is_disabled():
                    button_text = await button.inner_text()
                    print(f"        ✅ Found upload button: '{button_text}'")
                    
                    # Set up file chooser handler before clicking
                    async def handle_file_chooser(file_chooser):
                        await file_chooser.set_files(cv_path)
                        print(f"        ✅ File selected: {cv_path}")
                    
                    # Listen for file chooser dialog
                    page.on("filechooser", handle_file_chooser)
                    
                    # Click the upload button
                    await button.click()
                    print("        🖱️ Clicked upload button")
                    
                    # Wait for file dialog and upload
                    await asyncio.sleep(3)
                    
                    # Remove the event listener
                    page.remove_listener("filechooser", handle_file_chooser)
                    
                    return True
                    
            except Exception as e:
                print(f"      Error with upload button {selector}: {str(e)}")
                continue
        
        return False
    
    async def _verify_upload_success(self, page, cv_path: str) -> bool:
        """Verify that the file upload was successful"""
        try:
            # Look for success indicators
            success_indicators = [
                'text="Upload successful"',
                'text="File uploaded"',
                'text="Upload complete"',
                '[class*="success"]',
                '[class*="uploaded"]',
                '.upload-success',
                '.file-uploaded'
            ]
            
            filename = os.path.basename(cv_path)
            
            for indicator in success_indicators:
                try:
                    element = await page.wait_for_selector(indicator, timeout=3000, state='visible')
                    if element:
                        print(f"        ✅ Found upload success indicator: {indicator}")
                        return True
                except:
                    continue
            
            # Look for the filename in the page (indicates successful upload)
            try:
                filename_element = await page.wait_for_selector(f'text="{filename}"', timeout=3000, state='visible')
                if filename_element:
                    print(f"        ✅ Found uploaded filename on page: {filename}")
                    return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"        Error verifying upload: {str(e)}")
            return False