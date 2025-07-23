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
            'source--source': 'Company Website',
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
    
    async def _handle_radio_by_id(self, page, field_id: str, value: str) -> bool:
        """Handle radio buttons by finding the correct option"""
        
        try:
            # Find all radio buttons with this name/id
            radio_selectors = [
                f'input[name="{field_id}"]',
                f'input[data-automation-id="{field_id}"]'
            ]
            
            for selector in radio_selectors:
                radios = await page.query_selector_all(selector)
                
                if radios:
                    # Look for the specific value we want
                    for radio in radios:
                        if await radio.is_visible():
                            radio_value = await radio.get_attribute('value')
                            
                            # Exact match
                            if radio_value and radio_value.lower() == value.lower():
                                await radio.check()
                                return True
                            
                            # For Yes/No questions
                            if value.lower() == 'no' and radio_value and 'no' in radio_value.lower():
                                await radio.check()
                                return True
                            elif value.lower() == 'yes' and radio_value and 'yes' in radio_value.lower():
                                await radio.check()
                                return True
                    
                    # If no exact match found, don't select anything for Yes/No questions
                    break
            
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