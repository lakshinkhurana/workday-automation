#!/usr/bin/env python3
"""
Direct Form Filler - Enhanced with button-based dropdown support
"""

import os
import asyncio
from turtle import delay
from dotenv import load_dotenv
import datetime

load_dotenv()

class DirectFormFiller:
    """Direct form filling by id, data-automation-id, and name attributes with button dropdown support"""
    
    def __init__(self):
        self.filled_count = 0
        
        # Set up today's date for form filling
        from datetime import datetime
        today = datetime.now()
        today_month = str(today.month)
        today_day = str(today.day)
        today_year = str(today.year)
        today_full_date = f"{today_month}{today_day}{today_year}"
        
        # Direct mapping of field id to environment variable
        self.field_mappings = {
            # My Information page fields
            'name--legalName--firstName': os.getenv('REGISTRATION_FIRST_NAME', ''),
            'name--legalName--lastName': os.getenv('REGISTRATION_LAST_NAME', ''),
            'email': os.getenv('REGISTRATION_EMAIL', ''),
            'phoneNumber--phoneNumber': os.getenv('REGISTRATION_PHONE', ''),
            'phoneNumber--phoneDeviceType': 'Home',
            'phoneNumber--countryPhoneCode': '+1',
            'phoneNumber--extension': '',
            'country--country': 'United States',
            'source--source': os.getenv('JOB_BOARD',''),
            'candidateIsPreviousWorker': 'No',
            'address--addressLine1': os.getenv('ADDRESS', ''),
            'address--city': os.getenv('CITY', ''),
            'address--countryRegion': os.getenv('STATE', ''),
            'address--postalCode': os.getenv('POSTAL_CODE', ''),
            
            # Self Identity fields
            'selfIdentifiedDisabilityData--name': os.getenv('REGISTRATION_FIRST_NAME', '') + ' ' + os.getenv('REGISTRATION_LAST_NAME', ''),
            'selfIdentifiedDisabilityData--dateSignedOn-dateSectionMonth-input': today_month,
            'selfIdentifiedDisabilityData--dateSignedOn-dateSectionDay-input': today_day,
            'selfIdentifiedDisabilityData--dateSignedOn-dateSectionYear-input': today_year,
            'selfIdentifiedDisabilityData--employeeId': '',
            
            # # Date fields
            # 'dateSectionMonth-input': today_month,
            # 'dateSectionDay-input': today_day,
            # 'dateSectionYear-input': today_year,
            
            # Professional fields
            'currentCompany': os.getenv('CURRENT_COMPANY', ''),
            'currentRole': os.getenv('CURRENT_ROLE', ''),
            'skills': os.getenv('PRIMARY_SKILLS', ''),
            'education': os.getenv('EDUCATION_MASTERS', ''),
            'github': os.getenv('GITHUB_URL', ''),
            'workAuthorization': 'Yes',
            'visaStatus': 'US Citizen',
            'requiresSponsorship': 'No',

            # Personal info with button dropdown support
            'personalInfoPerson--gender': 'Female', 
            'personalInfoUS--gender':'Female', # This will use button dropdown handler
            'personalInfoUS--ethnicity': os.getenv('ETHNICITY', 'Asian'),
            'personalInfoUS--veteranStatus': os.getenv('VETERAN_STATUS', 'I AM NOT A VETERAN'),
            'personalInfoUS--disability': os.getenv('DISABILITY_STATUS', ''),
            
            # Terms and Conditions checkbox
            'termsAndConditions--acceptTermsAndAgreements': 'true',
        }
    
    async def fill_page_by_automation_id(self, page) -> int:
      """Fill all fields on page by finding them with id, data-automation-id, and name attributes"""
      print("  🎯 Direct form filling by id, data-automation-id, and name attributes...")
    
      await self._debug_page_fields(page)
    
      self.filled_count = 0
    
      # Check if we're on the Self Identity page
      is_self_identity_page = await self._is_self_identity_page(page)
      if is_self_identity_page:
        print("  🔍 Detected Self Identity page, switching to specialized handler...")
        success = await self.handle_self_identify_page(page)
        if success:
            self.filled_count += 1  # Count as one "field" for the page
            print("  ✅ Self Identity page handled successfully")
        else:
            print("  ⚠️ Failed to handle Self Identify page")
        return self.filled_count
    
    # Continue with regular field filling for other pages
      for field_id, value in self.field_mappings.items():
        if value:
            success = await self._fill_field_by_id(page, field_id, value)
            if success:
                self.filled_count += 1
                print(f"    ✅ {field_id}: {value}")
            else:
                print(f"    ⚠️ Not found: {field_id}")
    
      print(f"  ✅ Direct filling complete: {self.filled_count} fields filled")
      return self.filled_count

    async def _is_self_identity_page(self, page) -> bool:
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
            element = await page.query_selector(indicator)
            if element and await element.is_visible():
                print(f"    ✅ Found Self Identity page indicator: {indicator}")
                return True
          return False
      except Exception as e:
        print(f"    ❌ Error checking for Self Identity page: {str(e)}")
        return False
      
    async def _debug_page_fields(self, page):
        """Debug function to see what fields are actually on the page"""
        print("  🔍 Debugging: Looking for all form fields on page...")
        
        try:
            # Check for button dropdowns with aria-haspopup="listbox"
            button_dropdowns = await page.query_selector_all('button[aria-haspopup="listbox"]')
            print(f"    Found {len(button_dropdowns)} button dropdowns:")
            
            for i, button in enumerate(button_dropdowns[:5]):
                try:
                    button_id = await button.get_attribute('id')
                    button_name = await button.get_attribute('name')
                    button_value = await button.get_attribute('value')
                    aria_label = await button.get_attribute('aria-label')
                    button_text = await button.inner_text()
                    is_visible = await button.is_visible()
                    
                    print(f"      Button {i+1}: id='{button_id}', name='{button_name}', value='{button_value}', text='{button_text}', aria-label='{aria_label}', visible={is_visible}")
                except:
                    print(f"      Button {i+1}: Could not get attributes")
            
            # Regular inputs
            inputs = await page.query_selector_all('input')
            print(f"    Found {len(inputs)} input elements:")
            
            for i, input_elem in enumerate(inputs[:10]):
                try:
                    input_id = await input_elem.get_attribute('id')
                    input_name = await input_elem.get_attribute('name')
                    input_type = await input_elem.get_attribute('type')
                    data_automation_id = await input_elem.get_attribute('data-automation-id')
                    is_visible = await input_elem.is_visible()
                    
                    print(f"      Input {i+1}: id='{input_id}', name='{input_name}', type='{input_type}', data-automation-id='{data_automation_id}', visible={is_visible}")
                except:
                    print(f"      Input {i+1}: Could not get attributes")
            
            # Select elements
            selects = await page.query_selector_all('select')
            print(f"    Found {len(selects)} select elements:")
            
            for i, select_elem in enumerate(selects[:5]):
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
        
        # Check for existing value before filling
        try:
            # Check input fields
            input_selectors = [
                f'input[id="{field_id}"]',
                f'input[data-automation-id="{field_id}"]',
                f'input[name="{field_id}"]'
            ]
            for selector in input_selectors:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    current_value = await element.input_value()
                    if current_value.strip() == value.strip():
                        print(f"    ✅ Field '{field_id}' already has correct value: '{value}'")
                        return True
            
            # Check button dropdowns
            button_selectors = [
                f'button[id="{field_id}"]',
                f'button[data-automation-id="{field_id}"]'
            ]
            for selector in button_selectors:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    button_text = await element.inner_text()
                    if button_text.strip().lower() == value.strip().lower():
                        print(f"    ✅ Button '{field_id}' already has correct value: '{value}'")
                        return True
            
            # Check select elements
            select_selectors = [
                f'select[id="{field_id}"]',
                f'select[data-automation-id="{field_id}"]'
            ]
            for selector in select_selectors:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    selected_option = await element.evaluate('el => el.options[el.selectedIndex].text')
                    if selected_option and selected_option.strip().lower() == value.strip().lower():
                        print(f"    ✅ Select '{field_id}' already has correct value: '{value}'")
                        return True
        except Exception as e:
            print(f"    ⚠️ Error checking existing value: {str(e)}")
        
        # If no matching value found, proceed with filling
        
        # Check if this is a button dropdown first (highest priority)
        button_dropdown_success = await self._handle_button_dropdown_by_id(page, field_id, value)
        if button_dropdown_success:
            return True
        
        # Special handling for known dropdown fields
        if field_id == 'source--source':
            return await self._handle_source_dropdown_simple(page, field_id, value)
        
        if field_id == 'phoneNumber--phoneDeviceType':
            return await self._handle_phone_device_type_dropdown(page, field_id, value)
        
        # # Special handling for date fields
        # if any(date_field in field_id for date_field in ['selfIdentifiedDisabilityData--dateSignedOn-dateSectionMonth-input', 'selfIdentifiedDisabilityData--dateSignedOn-dateSectionDay-input', 'selfIdentifiedDisabilityData--dateSignedOn-dateSectionYear-input']):
        #     return await self._handle_date_simple_fill(page, field_id, value)

        if field_id == 'termsAndConditions--acceptTermsAndAgreements':
            return await self._handle_terms_checkbox(page, value)

        try:
            # Try text input fields
            text_selectors = [
                f'input[id="{field_id}"]',
                f'input[data-automation-id="{field_id}"]',
                f'input[name="{field_id}"]',
                f'input[id*="{field_id}"]',
                f'input[data-automation-id*="{field_id}"]'
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
                                if 'date' in field_id.lower() or field_id in ['dateSectionMonth-input', 'dateSectionDay-input', 'dateSectionYear-input']:
                                    await page.click(selector)
                                    await asyncio.sleep(0.3)
                                    await page.keyboard.press('Control+a')
                                    await asyncio.sleep(0.2)
                                    await page.keyboard.press('Delete')
                                    await asyncio.sleep(0.2)
                                    await page.type(selector, value, delay=100)
                                    await asyncio.sleep(0.5)
                                else:
                                    await page.wait_for_selector(selector, state='attached')
                                    await page.fill(selector, '')
                                    await page.fill(selector, value)
                                
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
            
            # Try select dropdown fields
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
            
            # Try textarea fields
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
                            await page.wait_for_selector(selector, state='attached')
                            await page.fill(selector, '')
                            await page.fill(selector, value)
                            
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
            
            # Radio button groups
            if field_id in ['candidateIsPreviousWorker', 'workAuthorization', 'requiresSponsorship']:
                print(f"      🔍 Handling radio button group for: {field_id}")
                return await self._handle_radio_by_id(page, field_id, value)
            
            print(f"    ❌ No matching element found for field: {field_id}")
            return False
            
        except Exception as e:
            print(f"    ❌ Critical error filling {field_id}: {str(e)}")
            return False
    
    async def _handle_button_dropdown_by_id(self, page, field_id: str, value: str) -> bool:
        """Handle button-based dropdowns with aria-haspopup='listbox' structure"""
        
        print(f"      🔍 Checking for button dropdown: {field_id}")
        
        try:
            # Try different selectors for button dropdowns
            button_selectors = [
                f'button[id="{field_id}"]',
                f'button[name="{field_id}"]',
                f'button[data-automation-id="{field_id}"]',
                f'button[id*="{field_id}"]',
                f'button[name*="{field_id}"]',
                f'button[data-automation-id*="{field_id}"]'
            ]
            
            for selector in button_selectors:
                try:
                    print(f"        🔍 Trying button selector: {selector}")
                    button_element = await page.query_selector(selector)
                    
                    if button_element and await button_element.is_visible():
                        # Check if it's a dropdown button
                        aria_haspopup = await button_element.get_attribute('aria-haspopup')
                        button_type = await button_element.get_attribute('type')
                        button_text = await button_element.inner_text()
                        
                        print(f"        Found button: aria-haspopup='{aria_haspopup}', type='{button_type}', text='{button_text}'")
                        
                        # Check if it's a listbox dropdown button
                        if aria_haspopup == 'listbox' or 'Select' in button_text or button_text.strip() == '':
                            print(f"        ✅ Found button dropdown with selector: {selector}")
                            
                            # Click the button to open dropdown
                            await button_element.click()
                            await asyncio.sleep(1)  # Wait for dropdown to open
                            print(f"        🖱️ Clicked button dropdown")
                            
                            # Look for dropdown options
                            success = await self._select_dropdown_option_from_listbox(page, value, field_id)
                            
                            if success:
                                print(f"    ✅ Successfully selected '{value}' from button dropdown '{field_id}'")
                                return True
                            else:
                                print(f"    ⚠️ Could not select '{value}' from button dropdown options")
                                
                                # Try pressing Escape to close dropdown if selection failed
                                try:
                                    await page.keyboard.press('Escape')
                                    await asyncio.sleep(0.5)
                                except:
                                    pass
                        else:
                            print(f"        Not a dropdown button (aria-haspopup='{aria_haspopup}')")
                            
                except Exception as e:
                    print(f"        Error with button selector {selector}: {str(e)}")
                    continue
            
            return False
            
        except Exception as e:
            print(f"        ❌ Error handling button dropdown {field_id}: {str(e)}")
            return False
    
    async def _select_dropdown_option_from_listbox(self, page, value: str, field_id: str) -> bool:
        """Select option from opened listbox dropdown"""
        
        print(f"        🔍 Looking for dropdown options with value '{value}'")
        
        try:
            # Wait for dropdown options to appear
            await asyncio.sleep(0.5)
            
            # Try different selectors for dropdown options
            option_selectors = [
                f'li:has-text("{value}")',  # List item with exact text
                f'div:has-text("{value}")',  # Div with exact text
                f'span:has-text("{value}")',  # Span with exact text
                f'[role="option"]:has-text("{value}")',  # ARIA option with exact text
                f'[role="listbox"] *:has-text("{value}")',  # Any element in listbox with exact text
                f'ul li:has-text("{value}")',  # List item in unordered list
                f'.option:has-text("{value}")',  # Element with option class
                f'[data-value="{value}"]',  # Element with data-value attribute
                f'[value="{value}"]'  # Element with value attribute
            ]
            
            # First try exact matches
            for option_selector in option_selectors:
                try:
                    print(f"          🔍 Trying exact option selector: {option_selector}")
                    option_element = await page.wait_for_selector(option_selector, timeout=3000, state='visible')
                    if option_element:
                        option_text = await option_element.inner_text()
                        print(f"          ✅ Found exact match option: '{option_text}'")
                        await option_element.click()
                        await asyncio.sleep(0.5)
                        return True
                except:
                    continue
            
            # If exact match not found, try partial matching
            print(f"        🔍 Trying partial text matching for '{value}'...")
            
            # Look for any visible dropdown options
            potential_option_selectors = [
                '[role="option"]',
                '[role="listbox"] li',
                '[role="listbox"] div',
                'ul li',
                '.option',
                '[data-testid*="option"]'
            ]
            
            for potential_selector in potential_option_selectors:
                try:
                    options = await page.query_selector_all(f'{potential_selector}:visible')
                    print(f"          🔍 Found {len(options)} potential options with selector: {potential_selector}")
                    
                    for i, option in enumerate(options[:10]):  # Limit to first 10 options
                        try:
                            option_text = await option.inner_text()
                            option_text_clean = option_text.strip().lower()
                            value_clean = value.strip().lower()
                            
                            print(f"            Option {i+1}: '{option_text}'")
                            
                            # Check for partial matches
                            if (value_clean in option_text_clean or 
                                option_text_clean in value_clean or
                                self._fuzzy_match(value_clean, option_text_clean)):
                                
                                print(f"          ✅ Found partial match: '{option_text}' matches '{value}'")
                                await option.click()
                                await asyncio.sleep(0.5)
                                return True
                                
                        except Exception as e:
                            print(f"            Error checking option {i+1}: {str(e)}")
                            continue
                            
                except Exception as e:
                    print(f"          Error with potential selector {potential_selector}: {str(e)}")
                    continue
            
            # Final fallback: try typing the value and pressing Enter
            print(f"        🔍 Fallback: trying to type '{value}' and press Enter")
            try:
                await page.keyboard.type(value, delay=1000)
                await asyncio.sleep(0.5)
                await page.keyboard.press('Enter')
                await asyncio.sleep(0.5)
                print(f"        ✅ Typed '{value}' and pressed Enter")
                return True
            except Exception as e:
                print(f"        ❌ Typing fallback failed: {str(e)}")
            
            return False
            
        except Exception as e:
            print(f"        ❌ Error selecting dropdown option: {str(e)}")
            return False
    
    def _fuzzy_match(self, value1: str, value2: str) -> bool:
        """Simple fuzzy matching for dropdown options"""
        
        # Remove common words and punctuation
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'not', 'select', 'one', 'choose', 'please'}
        
        def clean_text(text):
            import re
            # Remove punctuation and convert to lowercase
            text = re.sub(r'[^\w\s]', '', text.lower())
            # Split into words and remove stop words
            words = [word for word in text.split() if word not in stop_words and len(word) > 1]
            return set(words)
        
        words1 = clean_text(value1)
        words2 = clean_text(value2)
        
        if not words1 or not words2:
            return False
        
        # Check if there's significant overlap
        common_words = words1.intersection(words2)
        min_words = min(len(words1), len(words2))
        
        # At least 50% overlap for small sets, or at least 2 common words
        if min_words <= 2:
            return len(common_words) >= 1
        else:
            return len(common_words) / min_words >= 0.5
    
    # Keep all your existing methods (they're working fine)
    async def _handle_select_by_id(self, select_element, value: str) -> bool:
        """Handle select dropdown by trying different ways to select stuff"""
        
        try:
            await select_element.select_option(value=value)
            return True
        except:
            pass
        
        try:
            await select_element.select_option(label=value)
            return True
        except:
            pass
        
        try:
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
            button_selectors = [
                f'button[id="{field_id}"]',
                f'button[id="phoneNumber--phoneType"]',
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
                        
                        await page.click(selector)
                        await asyncio.sleep(1)
                        print(f"        🖱️ Clicked phone device type button")
                        
                        success = await self._select_dropdown_option_from_listbox(page, value, field_id)
                        if success:
                            return True
                        
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
            selector = f'input[id="{field_id}"]'
            
            print(f"        🔍 Trying source dropdown selector: {selector}")
            element = await page.query_selector(selector)
            
            if element and await element.is_visible():
                is_enabled = await element.is_enabled()
                print(f"        ✅ Found source element: enabled={is_enabled}")
                
                if is_enabled:
                    await page.click(selector)
                    await asyncio.sleep(0.3)
                    
                    await page.type(selector, value, delay=100)
                    await asyncio.sleep(0.5)
                    
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

    async def _handle_date_simple_fill(self, page, field_id: str, value: str) -> bool:
        """Handle date fields using simple fill method"""
        
        print(f"      🔍 Handling date field with simple fill for: {field_id}")
        
        try:
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
                            # Clear any existing value
                            await asyncio.sleep(0.3)
                            await page.fill(selector, value)
                            await asyncio.sleep(0.3)
                            
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
            
            radio_selectors = [
                f'input[name="{field_id}"]',
                f'input[id="{field_id}"]',
                f'input[data-automation-id="{field_id}"]'
            ]
            
            for selector in radio_selectors:
                print(f"        🔍 Trying radio selector: {selector}")
                radios = await page.query_selector_all(selector)
                
                if radios:
                    print(f"        ✅ Found {len(radios)} radio buttons with selector: {selector}")
                    
                    for i, radio in enumerate(radios):
                        if await radio.is_visible():
                            radio_value = await radio.get_attribute('value')
                            radio_id = await radio.get_attribute('id')
                            print(f"          Radio {i+1}: id='{radio_id}', value='{radio_value}'")
                    
                    # For candidateIsPreviousWorker, we want to select "No"
                    if field_id == 'candidateIsPreviousWorker' and value.lower() == 'no':
                        for radio in radios:
                            if await radio.is_visible():
                                radio_value = await radio.get_attribute('value')
                                radio_id = await radio.get_attribute('id')
                                
                                if radio_value and (
                                    radio_value.lower() == 'no' or 
                                    radio_value.lower() == 'false' or 
                                    radio_value == '0' or
                                    'no' in radio_value.lower()
                                ):
                                    await page.check(f'#{radio_id}')
                                    print(f"        ✅ Selected 'No' radio button: id='{radio_id}', value='{radio_value}'")
                                    return True
                        
                        if len(radios) >= 2:
                            second_radio = radios[1]
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
                            
                            if radio_value and radio_value.lower() == value.lower():
                                await page.check(f'#{radio_id}')
                                print(f"        ✅ Selected radio button with exact match: {radio_value}")
                                return True
                            
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
        except Exception as e:
          print(f"        ❌ Error handling radio buttons for {field_id}: {str(e)}")
          return False
            
    
    async def handle_self_identify_page(self, page) -> bool:
        """Handle Self Identify page - fill name, date, checkboxes and press Save and Continue"""
        print("  📊 Processing Self Identify page...")
        
        try:
            today = datetime.datetime.now()
            self_identity_fields = {
                'selfIdentifiedDisabilityData--name': os.getenv('REGISTRATION_FIRST_NAME', '') + ' ' + os.getenv('REGISTRATION_LAST_NAME', ''),
                'selfIdentifiedDisabilityData--employeeId': ''
            }
            self_identity_dates={
                'selfIdentifiedDisabilityData--dateSignedOn-dateSectionMonth-input': f"{str(today.month)}",
                'selfIdentifiedDisabilityData--dateSignedOn-dateSectionDay-input': f"{str(today.day)}",
                'selfIdentifiedDisabilityData--dateSignedOn-dateSectionYear-input': f"{str(today.year)}"
            }
            filled_count = 0
            
            for field_id, value in self_identity_fields.items():
                if value:
                    success = await self._fill_field_by_id(page, field_id, value)
                    if success:
                        filled_count += 1
                        print(f"    ✅ {field_id}: {value}")
                    else:
                        print(f"    ⚠️ Not found: {field_id}")

            for field_id, value in self_identity_dates.items():
                if value:
                    success = await self._handle_date_simple_fill(page, field_id, value) 
            await self._handle_disability_checkboxes(page)
            save_success = await self._press_save_and_continue(page)
            
            if save_success:
                print(f"  ✅ Self Identity page completed: {filled_count} fields filled, checkboxes handled, form submitted")
                return True
            else:
                print(f"  ⚠️ Self Identity page completed: {filled_count} fields filled, but could not submit form")
                return False
                
        except Exception as e:
            print(f"  ❌ Error handling Self Identity page: {str(e)}")
            return False
    
    async def _handle_disability_checkboxes(self, page) -> bool:
      """Handle disability status checkboxes on Self Identity page"""
      print("    🔲 Handling disability status checkboxes...")
    
      try:
          # Define all possible disability options in order of preference
          disability_options = [
              "I do not wish to answer",
              "I do not want to answer",
              "I prefer not to answer",
              "Choose not to identify",
              "Decline to answer",
              "Prefer not to disclose",
              "Do not wish to identify"
          ]

          # Try finding labels with specific text content
          for option in disability_options:
            try:
                # Use text content selectors
                label_selectors = [
                    f'label:has-text("{option}")',
                    f'[role="radio"]:has-text("{option}")',
                    f'div[role="radio"]:has-text("{option}")',
                    f'div:has-text("{option}") >> role=radio',
                    f'text="{option}"'
                ]

                for selector in label_selectors:
                    print(f"      🔍 Looking for: '{selector}'")
                    element = await page.query_selector(selector)
                    
                    if element and await element.is_visible():
                        # Try clicking the element
                        await element.click()
                        await asyncio.sleep(0.5)
                        print(f"      ✅ Clicked option: '{option}'")
                        return True

            except Exception as e:
                print(f"      ⚠️ Error processing option '{option}': {str(e)}")
                continue

          # Fallback: Try finding any visible radio buttons or labels with similar text
          print("    🔄 Trying fallback approach...")
          
          labels = await page.query_selector_all('label, [role="radio"]')
          for label in labels:
              if await label.is_visible():
                  try:
                      label_text = await label.inner_text()
                      label_text = label_text.strip().lower()
                      
                      # Check if label contains any of our keywords
                      keywords = ["not", "decline", "prefer", "don't", "do not", "choose not"]
                      if any(keyword in label_text for keyword in keywords):
                          await label.click()
                          await asyncio.sleep(0.5)
                          print(f"      ✅ Clicked fallback option: '{label_text}'")
                          return True
                          
                  except Exception as e:
                      continue

          print("    ⚠️ No matching disability options found")
          return False
            
      except Exception as e:
        print(f"    ❌ Error handling disability checkboxes: {str(e)}")
        return False
          
    async def _press_save_and_continue(self, page) -> bool:
        """Press Save and Continue button on Self Identity page"""
        print("    💾 Looking for Save and Continue/Submit button...")
        
        try:
            save_selectors = [
                'button[data-automation-id="pageFooterNextButton"]',  # Most specific selector first
                'button:has-text("Save and Continue")',
                'button:has-text("Save & Continue")',
                'button:has-text("Continue")',
                'button:has-text("Submit")',
                'button:has-text("Next")',
                'button:has-text("Save")',
                'button[type="submit"]',
                'input[type="submit"]',
                '[data-automation-id*="save"]',
                '[data-automation-id*="continue"]',
                '[data-automation-id*="next"]',
                '.css-1kttxua'  # Generic class selector as fallback
            ]
            
            for selector in save_selectors:
                try:
                    # Wait for element with longer timeout and ensure it's visible
                    element = await page.wait_for_selector(selector, timeout=5000, state='visible')
                    if element and not await element.is_disabled():
                        button_text = await element.inner_text()
                        print(f"    ✅ Found Save button: '{button_text}' using selector: {selector}")
                        
                        # Click and wait for network idle
                        await element.click()
                        print(f"    🖱️ Clicked Save and Continue button")
                        
                        print("    ⏳ Waiting for form submission and redirection...")
                        await asyncio.sleep(3)
                        await page.wait_for_load_state("networkidle", timeout=10000)
                        print("    ✅ Form submitted and page redirected")
                        
                        return True
                except Exception as e:
                    print(f"    ⚠️ Error with save selector {selector}: {str(e)}")
                    continue
            
            print(f"    ❌ Could not find Save and Continue button")
            return False
            
        except Exception as e:
            print(f"    ❌ Critical error pressing Save and Continue: {str(e)}")
            return False

    async def submit_form(self, page) -> bool:
        """Submit the form after filling"""
        
        print("  🚀 Submitting form...")
        
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
                    
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    await asyncio.sleep(2)
                    return True
            except:
                continue
        
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
            voluntary_fields = {
                'ethnicity': os.getenv('ETHNICITY', 'Prefer not to disclose'),
                'gender': os.getenv('GENDER', 'Prefer not to disclose'), 
                'veteran_status': os.getenv('VETERAN_STATUS', 'I am not a protected veteran'),
                'disability_status': os.getenv('DISABILITY_STATUS', 'I don\'t wish to answer'),
                'terms_checkbox': os.getenv('ACCEPT_TERMS', 'true')
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
            field_button_ids = {
                'ethnicity': 'personalInfoUS--ethnicity',
                'gender': 'personalInfoUS--gender',
                'veteran_status': 'personalInfoUS--veteranStatus',
                'disability_status': 'personalInfoUS--disability'
            }
            
            button_id = field_button_ids.get(field_type)
            
            if button_id:
                success = await self._handle_button_dropdown_by_id(page, button_id, value)
                if success:
                    return True
            
            if field_type == 'terms_checkbox':
                return await self._handle_terms_checkbox(page, value)
            
            print(f"    ❌ Could not find field for {field_type}")
            return False
            
        except Exception as e:
            print(f"    ❌ Error filling {field_type}: {str(e)}")
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
    
    async def handle_experience_page_uploads(self, page) -> bool:
        """Handle CV upload on My Experience page"""
        print("  📄 Processing My Experience page - looking for CV upload...")
        
        try:
            cv_path = os.getenv('RESUME_PATH', '')
            
            if not cv_path:
                print("    ⚠️ CV_FILE_PATH not found in .env file")
                return False
            
            if not os.path.exists(cv_path):
                print(f"    ❌ CV file not found at path: {cv_path}")
                return False
            
            print(f"    📁 Found CV file: {cv_path}")
            
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
            select_files_button = await page.query_selector('[data-automation-id="select-files"]')
            
            if select_files_button and await select_files_button.is_visible():
                print("    ✅ Found select-files button")
                
                async def handle_file_chooser(file_chooser):
                    await file_chooser.set_files(cv_path)
                    print(f"    ✅ File selected: {cv_path}")
                
                page.on("filechooser", handle_file_chooser)
                
                await select_files_button.click()
                print("    🖱️ Clicked select-files button")
                
                await asyncio.sleep(3)
                
                page.remove_listener("filechooser", handle_file_chooser)
                
                upload_confirmed = await self._verify_upload_success(page, cv_path)
                
                if upload_confirmed:
                    print("    ✅ Upload confirmed successful")
                    return True
                else:
                    print("    ✅ Upload completed (verification not available)")
                    return True
            
            else:
                print("    ⚠️ select-files button not found, trying fallback methods...")
                return await self._try_fallback_upload_methods(page, cv_path)
                
        except Exception as e:
            print(f"    ❌ Error with select-files button: {str(e)}")
            return await self._try_fallback_upload_methods(page, cv_path)
    
    async def _try_fallback_upload_methods(self, page, cv_path: str) -> bool:
        """Fallback methods for CV upload if select-files button not found"""
        print("    🔍 Trying fallback upload methods...")
        
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
                
                file_inputs = await page.query_selector_all(selector)
                
                for j, file_input in enumerate(file_inputs):
                    try:
                        is_visible = await file_input.is_visible()
                        is_enabled = await file_input.is_enabled()
                        input_type = await file_input.get_attribute('type')
                        accept_attr = await file_input.get_attribute('accept')
                        
                        print(f"        Input {j+1}: visible={is_visible}, enabled={is_enabled}, type={input_type}, accept={accept_attr}")
                        
                        if input_type == 'file' and is_enabled:
                            await file_input.set_input_files(cv_path)
                            print(f"        ✅ Successfully uploaded CV using selector: {selector}")
                            
                            await asyncio.sleep(2)
                            
                            upload_confirmed = await self._verify_upload_success(page, cv_path)
                            
                            if upload_confirmed:
                                print("        ✅ Upload confirmed successful")
                                return True
                            else:
                                print("        ⚠️ Upload may have succeeded but couldn't verify")
                                return True
                        
                    except Exception as e:
                        print(f"        Error with file input {j+1}: {str(e)}")
                        continue
                        
            except Exception as e:
                print(f"      Error with selector {selector}: {str(e)}")
                continue
        
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
                    
                    async def handle_file_chooser(file_chooser):
                        await file_chooser.set_files(cv_path)
                        print(f"        ✅ File selected: {cv_path}")
                    
                    page.on("filechooser", handle_file_chooser)
                    
                    await button.click()
                    print("        🖱️ Clicked upload button")
                    
                    await asyncio.sleep(3)
                    
                    page.remove_listener("filechooser", handle_file_chooser)
                    
                    return True
                    
            except Exception as e:
                print(f"      Error with upload button {selector}: {str(e)}")
                continue
        
        return False
    
    async def _verify_upload_success(self, page, cv_path: str) -> bool:
        """Verify that the file upload was successful"""
        try:
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

    async def check_for_success_url(self, page) -> bool:
        """Check if current URL matches the success URL"""
        try:
            # Get success URL from environment
            success_url = os.getenv('WORKDAY_END_URL', '')
            if not success_url:
                print("  ⚠️ No success URL configured in environment")
                return False

            # Wait for URL to potentially change (max 10 seconds)
            print("  🔍 Checking for successful completion URL...")
            try:
                await page.wait_for_url(success_url, timeout=10000)
                print("  ✅ Success URL detected! Application completed successfully")
                return True
            except Exception:
                current_url = page.url
                print(f"  ℹ️ Current URL: {current_url}")
                print(f"  ℹ️ Expected URL: {success_url}")
                
                # Check if current URL contains success URL components
                if success_url.lower() in current_url.lower():
                    print("  ✅ Success URL pattern detected! Application completed successfully")
                    return True
                
                print("  ❌ Success URL not detected")
                return False

        except Exception as e:
            print(f"  ❌ Error checking success URL: {str(e)}")
            return False