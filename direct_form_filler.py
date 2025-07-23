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
            'source--source': 'vidyapeeth',
            'candidateIsPreviousWorker': 'No',  # Radio button for previous employee
            
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
        
        # Special handling for dropdown fields that need typing + Enter
        if field_id == 'source--source':
            return await self._handle_dropdown_with_typing(page, field_id, value)
        
        # Special handling for phone device type dropdown
        if field_id == 'phoneNumber--phoneDeviceType':
            return await self._handle_phone_device_type_dropdown(page, field_id, value)
        
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
                        
                        # Click to focus the field
                        await page.click(selector)
                        await asyncio.sleep(0.5)
                        
                        # Clear any existing value
                        await page.fill(selector, '')
                        await asyncio.sleep(0.5)
                        
                        # Type the value
                        await page.type(selector, value)
                        await asyncio.sleep(1)
                        
                        # Press Enter to select
                        await page.keyboard.press('Enter')
                        await asyncio.sleep(1)
                        
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