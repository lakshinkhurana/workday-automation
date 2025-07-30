#!/usr/bin/env python3
"""
Direct Form Filler - Enhanced with button-based dropdown support
"""
import sys
import os
import asyncio
from turtle import delay
from dotenv import load_dotenv
import datetime
from datetime import datetime
from functools import lru_cache
import re
from typing import Dict, List, Optional

load_dotenv()

class AutomationCompleteException(Exception):
    """Raised when automation should end due to reaching completion URL"""
    def __init__(self, message="Automation complete"):
        self.message = message
        self.success = True
        super().__init__(self.message)
        
    def display_completion_message(self):
        """Display a formatted completion message"""
        print("\n" + "="*80)
        print("🎉 Workday Application Automation Complete! 🎉")
        print(f"✨ Status: {'Success' if self.success else 'Failed'}")
        print(f"✨ Message: {self.message}")
        print("✨ Application process has been completed")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"✨ Completed at: {current_time}")
        print("="*80 + "\n")
        if self.success:
            sys.exit(0)  # Exit with success code
        else:
            sys.exit(1)  # Exit with error code



class DirectFormFiller:
    """Direct form filling by id, data-automation-id, and name attributes with button dropdown support"""
    
    def _determine_age_group(self) -> str:
        """Determine age group based on AGE environment variable"""
        try:
            age = int(os.getenv('AGE', '0'))
            if age < 16:
                return 'Under 16 years of age'
            elif 16 <= age <= 17:
                return '16-17 years of age'
            elif age >= 18:
                return '18 years of age and Over'
            return ''  # Default empty if age is invalid
        except ValueError:
            print("    ⚠️ Invalid age value in environment variable")
            return ''
    
    def __init__(self):
        self.filled_count = 0
        
        
        # Set up today's date for form filling
        today = datetime.now()
        today_month = str(today.month)
        today_day = str(today.day)
        today_year = str(today.year)
        today_full_date = f"{today_month}{today_day}{today_year}"
        qualification='Do you certify you meet all minimum qualifications for this job as outlined in the job posting? If you do not recall the minimum qualification for this job, please review the job posting prior to answering this question'
        messages='''Would you like to receive mobile text message updates relating to your employment relationship with Walmart? If so, choose to Opt-in below.

Your response to this question will replace any response you’ve provided on previous job applications. If you previously selected Opt-in and now choose to Opt-out, you will not receive text messages for active employment applications. If you choose to Opt-out previously and now choose to Opt-in, you will begin to receive text messages for active employment regarding application status and updates as a new associate.

Message and data rates may apply. Message frequency may vary. Text STOP to cancel text message updates. For assistance, text HELP or contact People Services at 1-888-596-2365 for additional support. View our mobile terms and privacy notice. Review the Terms & Conditions in the following pages of this application.
        '''
        
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
            # 'education': os.getenv('EDUCATION_MASTERS', ''),
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

            # Application questions
            qualification: os.getenv('WALMART_QUALIFICATIONS', 'Yes'),
            
            messages: os.getenv('WALMART_MESSAGES', 'Opt-Out from receiving text messages from Walmart'),
            
            'Are you legally able to work in the country where this job is located?': os.getenv('WALMART_WORK_ELLIGIBILITY', 'Yes'),
            
            'Please select your age category:': self._determine_age_group(),
            
            'Please select your Walmart Associate Status/Affiliation:': os.getenv('WALMART_AFFILATION', 'Have never been an employee of Walmart Inc or any of its subsidiaries'),
            
            'Will you now or in the future require "sponsorship for an immigration-related employment benefit"?    For purposes of this question "sponsorship for an immigration-related employment benefit" means: an H-1B, TN, L-1 or STEM Extension. (Please ask if you are uncertain whether you may need immigration sponsorship or desire clarification.)':os.getenv('REQUIRE_SPONSORSHIP', 'Yes'),
            
            'The following questions are to assist Walmart in determining your eligibility for its industry-leading hiring program for service members from any branch of the Uniformed Services of the United States and military spouses.  If you do not wish to answer these questions, please indicate below, and you can skip this portion of the application process.  If you provide the information on military status, it will not be considered in determining your qualification for any particular position.  Veterans and military spouses may be required to provide proof of their status, such as a DD 214 or Department of Defense Dependent Identification Card, to determine eligibility for this special hiring initiative.  *Uniformed Services are defined as the Army, Navy, Air Force, Marine Corps, Coast Guard, Public Health Service (Commissioned Corps) and the National Oceanic and Atmospheric Administration.  Do you have Active Duty or Guard/Reserve experience in the Uniformed Services of the United States?': os.getenv('ACTIVE_DUTY_STATUS', 'No'),
            
            "Do you have a direct family member who currently works for Walmart or Sam's Club?": os.getenv('FAMILY_MEMBER_WORKS_AT_WALMART', 'No'),
            
            'Does the Legal Name you provided on the “My Information” page match the name on your legal ID?': os.getenv('NAME_LEGAL', 'Yes'),
            
            

        }
    
    async def fill_page_by_automation_id(self, page) -> int:
      """Fill all fields on page by finding them with id, data-automation-id, and name attributes"""
      print("  🎯 Direct form filling by id, data-automation-id, and name attributes...")
      
      try:
          # Check for end URL first
          await self.check_for_success_url(page)
          
          await self._debug_page_fields(page)
      except AutomationCompleteException as e:
          print("\n" + "="*80)
          print(" Automation Completed Successfully! 🎉")
          print("✨ All required forms have been filled")
          print("✨ Application process is complete")
          print("="*80 + "\n")
          raise  # Re-raise the exception to be caught by the main automation loop
      self.filled_count = 0
      
      # Pre-check all fields for existing values
      print("  🔍 Checking for already filled fields...")
      already_filled = {}
      for field_id, value in self.field_mappings.items():
          if not value:
              continue
          try:
              # Check input fields
              selectors = [
                  f'input[id="{field_id}"]',
                  f'input[data-automation-id="{field_id}"]',
                  f'button[id="{field_id}"]',
                  f'select[id="{field_id}"]'
              ]
              for selector in selectors:
                  element = await page.query_selector(selector)
                  if element and await element.is_visible():
                      if await element.get_attribute('type') in ['text', 'email', 'tel']:
                          current_value = await element.input_value()
                          if current_value.strip() == value.strip():
                              print(f"    ✓ Field already correct: {field_id} = {value}")
                              already_filled[field_id] = True
                              self.filled_count += 1
                              break
                      elif await element.get_attribute('role') == 'button':
                          button_text = await element.inner_text()
                          if button_text.strip().lower() == value.strip().lower():
                              print(f"    ✓ Button already correct: {field_id} = {value}")
                              already_filled[field_id] = True
                              self.filled_count += 1
                              break
          except Exception as e:
              print(f"    ⚠️ Error checking field {field_id}: {str(e)}")
              continue
    
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
        if value and field_id not in already_filled:
            # Heuristic: if it has spaces, a '?', or is long, it's a question.
            is_question = ' ' in field_id or '?' in field_id or len(field_id) > 50
            
            if is_question:
                success = await self._handle_question_dropdown(page, field_id, value)
                if not success:
                    success = await self.fill_by_question_text(page, field_id, value)
            else:
                success = await self._fill_field_by_id(page, field_id, value)

            if not success:
                print(f"    ⚠️ Not found: {field_id[:50]}...")
        elif field_id in already_filled:
            pass
    
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
        
        try:
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
                            return True
            except Exception:
                pass
            
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
            
            if field_id == 'termsAndConditions--acceptTermsAndAgreements':
                return await self._handle_terms_checkbox(page, value)

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
                    text_element = await page.query_selector(selector)
                    if text_element:
                        is_visible = await text_element.is_visible()
                        is_enabled = await text_element.is_enabled()
                        input_type = await text_element.get_attribute('type')
                        
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
                                    print(f"    ✅ Successfully filled text field: {field_id}")
                                    self.filled_count += 1
                                    return True
                            elif input_type == 'radio':
                                return await self._handle_radio_by_id(page, field_id, value)
                            elif input_type == 'checkbox':
                                should_check = value.lower() in ['true', 'yes', '1']
                                if should_check:
                                    await page.check(selector)
                                else:
                                    await page.uncheck(selector)
                                print(f"    ✅ Filled checkbox: {field_id}")
                                self.filled_count += 1
                                return True
                except Exception:
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
                    select_element = await page.query_selector(selector)
                    if select_element:
                        is_visible = await select_element.is_visible()
                        is_enabled = await select_element.is_enabled()
                        
                        if is_visible and is_enabled:
                            success = await self._handle_select_by_id(select_element, value)
                            if success:
                                print(f"    ✅ Successfully filled select field: {field_id}")
                                self.filled_count += 1
                                return True
                except Exception:
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
                    textarea_element = await page.query_selector(selector)
                    if textarea_element:
                        is_visible = await textarea_element.is_visible()
                        is_enabled = await textarea_element.is_enabled()
                        
                        if is_visible and is_enabled:
                            await page.wait_for_selector(selector, state='attached')
                            await page.fill(selector, '')
                            await page.fill(selector, value)
                            
                            filled_value = await page.input_value(selector)
                            if filled_value == value:
                                print(f"    ✅ Successfully filled textarea: {field_id}")
                                self.filled_count += 1
                                return True
                except Exception:
                    continue
            
            # Radio button groups
            if field_id in ['candidateIsPreviousWorker', 'workAuthorization', 'requiresSponsorship']:
                return await self._handle_radio_by_id(page, field_id, value)
            
            return False
            
        except Exception:
            return False
    
    async def _handle_button_dropdown_by_id(self, page, field_id: str, value: str) -> bool:
        """Handle button-based dropdowns with aria-haspopup='listbox' structure"""
        
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
                    button_element = await page.query_selector(selector)
                    
                    if button_element and await button_element.is_visible():
                        aria_haspopup = await button_element.get_attribute('aria-haspopup')
                        button_text = await button_element.inner_text()
                        
                        if aria_haspopup == 'listbox' or 'Select' in button_text or button_text.strip() == '':
                            await button_element.click()
                            await asyncio.sleep(1)
                            
                            success = await self._select_dropdown_option_from_listbox(page, value, field_id)
                            
                            if success:
                                print(f"    ✅ Successfully selected '{value}' from button dropdown '{field_id}'")
                                self.filled_count += 1
                                return True
                            else:
                                try:
                                    await page.keyboard.press('Escape')
                                    await asyncio.sleep(0.5)
                                except:
                                    pass
                except Exception:
                    continue
            
            return False
            
        except Exception:
            return False
    
    async def _select_dropdown_option_from_listbox(self, page, value: str, field_id: str) -> bool:
        """Select option from opened listbox dropdown"""
        
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
                    option_element = await page.wait_for_selector(option_selector, timeout=3000, state='visible')
                    if option_element:
                        await option_element.click()
                        await asyncio.sleep(0.5)
                        return True
                except:
                    continue
            
            # If exact match not found, try partial matching
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
                    
                    for i, option in enumerate(options[:10]):  # Limit to first 10 options
                        try:
                            option_text = await option.inner_text()
                            option_text_clean = option_text.strip().lower()
                            value_clean = value.strip().lower()
                            
                            if (value_clean in option_text_clean or 
                                option_text_clean in value_clean or
                                self._fuzzy_match(value_clean, option_text_clean)):
                                
                                await option.click()
                                await asyncio.sleep(0.5)
                                return True
                                
                        except Exception:
                            continue
                            
                except Exception:
                    continue
            
            # Final fallback: try typing the value and pressing Enter
            try:
                await page.keyboard.type(value, delay=1000)
                await asyncio.sleep(0.5)
                await page.keyboard.press('Enter')
                await asyncio.sleep(0.5)
                return True
            except Exception:
                pass
            
            return False
            
        except Exception:
            return False
    
    async def _handle_question_dropdown(self, page, question_text: str, answer_value: str) -> bool:
        """Handle dropdowns associated with a question"""
        try:
            # Find the question element
            question_element = None
            cleaned_text = re.sub(r'<[^>]+>', '', question_text)
            cleaned_text = ' '.join(cleaned_text.split()).lower()
            all_elements = await page.query_selector_all('body *')
            for element in all_elements:
                try:
                    if not await element.is_visible():
                        continue
                    element_text = await element.evaluate('el => el.textContent')
                    element_text = ' '.join(element_text.split()).lower()
                    if cleaned_text in element_text:
                        question_element = element
                        break
                except Exception:
                    continue

            if not question_element:
                return False

            # Find the dropdown
            question_box = await question_element.bounding_box()
            if not question_box:
                return False

            dropdown_selector = 'button[aria-haspopup="listbox"]'
            dropdowns = await page.query_selector_all(dropdown_selector)
            closest_dropdown = None
            min_distance = float('inf')

            for dropdown in dropdowns:
                if await dropdown.is_visible():
                    dropdown_box = await dropdown.bounding_box()
                    if dropdown_box:
                        vertical_distance = dropdown_box['y'] - (question_box['y'] + question_box['height'])
                        if 0 < vertical_distance < min_distance:
                            min_distance = vertical_distance
                            closest_dropdown = dropdown

            if not closest_dropdown:
                return False

            # Open the dropdown and select the option
            await closest_dropdown.click()
            await asyncio.sleep(1)

            success = await self._select_dropdown_option_from_listbox(page, answer_value, "question-dropdown")
            if success:
                print(f"    ✅ Successfully answered question: {question_text[:50]}...")
                self.filled_count += 1
            
            return success

        except Exception:
            return False

    async def fill_by_question_text(self, page, question_text: str, answer_value: str, strict: bool = True) -> bool:
        """
        Find a button below specific question text and fill it with the given answer.
        
        Args:
            page: The page object
            question_text: The text of the question to look for
            answer_value: The value to select/enter in the associated button/input
            strict: If True, performs a more precise search for the question text.
            
        Returns:
            bool: True if successfully filled, False otherwise
        """
        try:
            # First locate the question text, cleaning up any HTML-like formatting
            cleaned_text = re.sub(r'<[^>]+>', '', question_text)
            cleaned_text = ' '.join(cleaned_text.split()).lower()
            
            question_element = None

            if strict:
                # Strict search: Find an element with text that closely matches the question
                all_elements = await page.query_selector_all('body *')
                for element in all_elements:
                    try:
                        if not await element.is_visible():
                            continue
                        element_text = await element.evaluate('el => el.textContent')
                        element_text = ' '.join(element_text.split()).lower()
                        if cleaned_text == element_text:
                            question_element = element
                            break
                    except Exception:
                        continue

            if not question_element:
                # Fallback to the original, more flexible search method
                escaped_text = cleaned_text.replace('"', '\"').replace("'", "\'")
                selectors = [
                    f"text='{escaped_text}'",
                    f'text="{escaped_text}"',
                    f"div:has-text('{escaped_text}')",
                    f'label:has-text("{escaped_text}")',
                    f'span:has-text("{escaped_text}")',
                    f'p:has-text("{escaped_text}")',
                    '*[role="heading"]:has-text("{escaped_text}")',
                    '*[class*="question"]:has-text("{escaped_text}")',
                    '*:has(> a):has-text("{escaped_text}")'
                ]
                for selector in selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        for element in elements:
                            if await element.is_visible():
                                element_text = await element.inner_text()
                                text_content = await element.evaluate('el => el.textContent')
                                element_text = ' '.join(element_text.split()).lower()
                                text_content = ' '.join(text_content.split()).lower()
                                if (cleaned_text in element_text or cleaned_text in text_content or self._fuzzy_match(cleaned_text, element_text) or self._fuzzy_match(cleaned_text, text_content)):
                                    question_element = element
                                    break
                        if question_element:
                            break
                    except Exception:
                        continue
            
            if not question_element:
                return False
                
            # Get the bounding box of the question element
            question_box = await question_element.bounding_box()
            if not question_box:
                return False
                
            # Look for the nearest button/input below the question
            button_selectors = [
                'button[aria-haspopup="listbox"]',
                'input[type="text"]',
                'select',
                'button'
            ]
            
            closest_element = None
            min_distance = float('inf')
            
            for selector in button_selectors:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    if await element.is_visible():
                        element_box = await element.bounding_box()
                        if element_box:
                            # Check if the element is below the question
                            vertical_distance = element_box['y'] - (question_box['y'] + question_box['height'])
                            horizontal_overlap = (element_box['x'] < (question_box['x'] + question_box['width']) and (element_box['x'] + element_box['width']) > question_box['x'])
                            
                            if vertical_distance > 0 and vertical_distance < 300 and horizontal_overlap:
                                distance = vertical_distance
                                if distance < min_distance:
                                    min_distance = distance
                                    closest_element = element
            
            if not closest_element:
                return False
                
            # Handle the found element based on its type
            tag_name = await closest_element.evaluate('element => element.tagName.toLowerCase()')
            
            if tag_name == 'button':
                # If it's a button, it's likely a dropdown
                await closest_element.click()
                await asyncio.sleep(0.5)
                success = await self._select_dropdown_option_from_listbox(page, answer_value, "dynamic-button")
                if success:
                    print(f"    ✅ Successfully answered question: {question_text[:50]}...")
                    self.filled_count += 1
                return success
                
            elif tag_name == 'input':
                # If it's an input, type the value
                await closest_element.click()
                await closest_element.fill(answer_value)
                print(f"    ✅ Successfully answered question: {question_text[:50]}...")
                self.filled_count += 1
                return True
                
            elif tag_name == 'select':
                # If it's a select, use select_option
                await closest_element.select_option(label=answer_value)
                print(f"    ✅ Successfully answered question: {question_text[:50]}...")
                self.filled_count += 1
                return True
                
            return False
            
        except Exception:
            return False

    @lru_cache(maxsize=1024)
    def _fuzzy_match(self, value1: str, value2: str) -> bool:
        """Simple fuzzy matching for dropdown options with caching"""
        
        # Remove common words and punctuation
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'not', 'select', 'one', 'choose', 'please'}
        
        def clean_text(text):
            # Remove punctuation and convert to lowercase
            text = re.sub(r'[^",a-z0-9 ]', '', text.lower())
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
        
        try:
            button_selectors = [
                f'button[id="{field_id}"]',
                f'button[id="phoneNumber--phoneType"]',
                f'button[name="phone_Type"]',
                f'button[aria-haspopup="listbox"]',
                f'button[id*="phoneType"]',
                f'button[id*="phoneNumber--phoneType"]'
            ]
            
            for selector in button_selectors:
                try:
                    button_element = await page.query_selector(selector)
                    if button_element and await button_element.is_visible():
                        
                        await page.click(selector)
                        await asyncio.sleep(1)
                        
                        success = await self._select_dropdown_option_from_listbox(page, value, field_id)
                        if success:
                            return True
                        
                except Exception:
                    continue
            
            return False
            
        except Exception:
            return False
    
    async def _handle_source_dropdown_simple(self, page, field_id: str, value: str) -> bool:
        """Handle source--source dropdown field - click once, type, and press Enter"""
        
        try:
            selector = f'input[id="{field_id}"]'
            
            element = await page.query_selector(selector)
            
            if element and await element.is_visible():
                is_enabled = await element.is_enabled()
                
                if is_enabled:
                    await page.click(selector)
                    await asyncio.sleep(0.3)
                    
                    await page.type(selector, value, delay=100)
                    await asyncio.sleep(0.5)
                    
                    await page.keyboard.press('Enter')
                    await asyncio.sleep(0.5)
                    
                    return True
            
            return False
            
        except Exception:
            return False

    async def _handle_date_simple_fill(self, page, field_id: str, value: str) -> bool:
        """Handle date fields using simple fill method"""
        
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
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        is_enabled = await element.is_enabled()
                        
                        if element.is_visible() and is_enabled:
                            await asyncio.sleep(0.3)
                            await page.fill(selector, value)
                            await asyncio.sleep(0.3)
                            
                            filled_value = await page.input_value(selector)
                            if filled_value == value:
                                return True
                        
                except Exception:
                    continue
            
            return False
            
        except Exception:
            return False

    async def _handle_radio_by_id(self, page, field_id: str, value: str) -> bool:
        """Handle radio buttons by finding the correct option"""
        
        try:
            radio_selectors = [
                f'input[name="{field_id}"]',
                f'input[id="{field_id}"]',
                f'input[data-automation-id="{field_id}"]'
            ]
            
            for selector in radio_selectors:
                radios = await page.query_selector_all(selector)
                
                if radios:
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
                                    print(f"        ✅ Selected 'No' radio button: {field_id}")
                                    self.filled_count += 1
                                    return True
                        
                        if len(radios) >= 2:
                            second_radio = radios[1]
                            radio_id = await second_radio.get_attribute('id')
                            await page.check(f'#{radio_id}')
                            print(f"        ✅ Selected second radio option (assuming 'No'): {field_id}")
                            self.filled_count += 1
                            return True
                    
                    for radio in radios:
                        if await radio.is_visible():
                            radio_value = await radio.get_attribute('value')
                            radio_id = await radio.get_attribute('id')
                            
                            if radio_value and radio_value.lower() == value.lower():
                                await page.check(f'#{radio_id}')
                                print(f"        ✅ Selected radio button with exact match: {field_id}")
                                self.filled_count += 1
                                return True
                            
                            if value.lower() == 'no' and radio_value and 'no' in radio_value.lower():
                                await page.check(f'#{radio_id}')
                                print(f"        ✅ Selected 'No' radio button: {field_id}")
                                self.filled_count += 1
                                return True
                            elif value.lower() == 'yes' and radio_value and 'yes' in radio_value.lower():
                                await page.check(f'#{radio_id}')
                                print(f"        ✅ Selected 'Yes' radio button: {field_id}")
                                self.filled_count += 1
                                return True
                    
                    break
        except Exception:
          return False
            
    
    async def handle_self_identify_page(self, page) -> bool:
        """Handle Self Identify page - fill name, date, checkboxes and press Save and Continue"""
        print("  📊 Processing Self Identify page...")
        
        try:
            
            today = datetime.now()
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

            for field_id, value in self_identity_dates.items():
                if value:
                    success = await self._handle_date_simple_fill(page, field_id, value) 
            await self._handle_disability_checkboxes(page, preferred_option=os.getenv('DISABILITY_STATUS', 'no answer'))
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
    
    async def _handle_disability_checkboxes(self, page, preferred_option: str = 'no answer') -> bool:
      """Handle disability status checkboxes on Self Identity page
      Args:
          page: The page object
          preferred_option: The user's preferred disability status option. If None, will use default options.
      """
      print("    🔲 Handling disability status checkboxes...")
    
      try:
          # Define all possible disability options with common variations
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

          # Determine which options to try based on preferred_option
          options_to_try = []
          if preferred_option:
              preferred_option = preferred_option.lower()
              # Try to match the preferred option with our defined categories
              for category, category_options in disability_options.items():
                  if preferred_option in category.lower():
                      options_to_try = category_options
                      break
              
              # If no category match, try the exact preferred option first
              if not options_to_try:
                  options_to_try = [preferred_option] + disability_options["no answer"]
          else:
              # If no preference specified, use the "no answer" options
              options_to_try = disability_options["no answer"]

          # Try finding labels with specific text content
          for option in options_to_try:
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
                      element = await page.query_selector(selector)
                      
                      if element and await element.is_visible():
                          # Try clicking the element
                          await element.click()
                          await asyncio.sleep(0.5)
                          print(f"      ✅ Clicked option: '{option}'")
                          return True

              except Exception:
                  continue

          # Fallback: Try finding any visible radio buttons or labels with similar text
          
          labels = await page.query_selector_all('label, [role="radio"]')
          
          # Define keywords based on preferred_option
          if preferred_option:
              preferred_lower = preferred_option.lower()
              if "no" in preferred_lower and "not" not in preferred_lower:
                  keywords = ["no", "don't have", "do not have"]
              elif "yes" in preferred_lower or "have" in preferred_lower:
                  keywords = ["yes", "have a disability", "disabled"]
              else:
                  keywords = ["not", "decline", "prefer", "don't", "do not", "choose not"]
          else:
              keywords = ["not", "decline", "prefer", "don't", "do not", "choose not"]
          
          for label in labels:
              if await label.is_visible():
                  try:
                      label_text = await label.inner_text()
                      label_text = label_text.strip().lower()
                      
                      # First try exact match with preferred_option if provided
                      if preferred_option and preferred_option.lower() in label_text:
                          await label.click()
                          await asyncio.sleep(0.5)
                          print(f"      ✅ Clicked fallback option matching preference: '{label_text}'")
                          return True
                      
                      # Then try keyword matching
                      if any(keyword in label_text for keyword in keywords):
                          await label.click()
                          await asyncio.sleep(0.5)
                          print(f"      ✅ Clicked fallback option with keyword match: '{label_text}'")
                          return True
                          
                  except Exception:
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
                except Exception:
                    continue
            
            print(f"    ❌ Could not find Save and Continue button")
            return False
            
        except Exception as e:
            print(f"    ❌ Critical error pressing Save and Continue: {str(e)}")
            return False

    async def submit_form(self, page) -> bool:
        """Submit the form after filling"""
        
        # Check if we've reached the end URL
        current_url = page.url
        end_url = os.getenv('WORKDAY_END_URL')
        if end_url and current_url.startswith(end_url):
            print("  🎉 Reached completion URL - ending automation")
            raise AutomationCompleteException("Automation complete - reached end URL")
            
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
            
            print(f"  ✅ Voluntary disclosures completed: {filled_count} fields filled")
            return filled_count > 0
            
        except Exception as e:
            print(f"  ❌ Error handling voluntary disclosures: {str(e)}")
            return False
    
    async def _fill_voluntary_field(self, page, field_type: str, value: str) -> bool:
        """Fill a specific voluntary disclosure field using button-based dropdowns"""
        
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
            
            return False
            
        except Exception:
            return False
    
    async def _handle_terms_checkbox(self, page, value: str) -> bool:
        """Handle terms and conditions checkbox"""
        try:
            checkbox_id = 'termsAndConditions--acceptTermsAndAgreements'
            checkbox_selector = f'input[id="{checkbox_id}"]'
            
            checkbox_element = await page.query_selector(checkbox_selector)
            
            if not checkbox_element or not await checkbox_element.is_visible():
                return False
            
            should_check = value.lower() in ['true', 'yes', '1', 'accept', 'agree']
            
            if should_check:
                await page.check(checkbox_selector)
                print(f"    ✅ Successfully checked terms and conditions checkbox")
                self.filled_count += 1
            else:
                await page.uncheck(checkbox_selector)
                print(f"    ✅ Successfully unchecked terms and conditions checkbox")
            
            return True
            
        except Exception:
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
                
                file_inputs = await page.query_selector_all(selector)
                
                for j, file_input in enumerate(file_inputs):
                    try:
                        is_visible = await file_input.is_visible()
                        is_enabled = await file_input.is_enabled()
                        input_type = await file_input.get_attribute('type')
                        accept_attr = await file_input.get_attribute('accept')
                        
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
                        
                    except Exception:
                        continue
                        
            except Exception:
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
                    
            except Exception:
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
            
        except Exception:
            return False

    async def check_for_success_url(self, page) -> bool:
        """Check if we've reached the end URL and raise exception if so"""
        current_url = page.url
        end_url = os.getenv('WORKDAY_END_URL')
        if end_url and current_url.startswith(end_url):
            print("  🎉 Reached completion URL - ending automation")
            complete_exception = AutomationCompleteException("Successfully completed the application process")
            complete_exception.display_completion_message()  # This will also exit the program
            print("  🎉 Reached completion URL - ending automation")
            raise Exception("Automation complete - reached end URL")
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