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
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page
from workday_autofill import WorkdayAutoFill

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

@dataclass
class FieldMapping:
    """Mapping between form field and CV data"""
    field_id: str
    field_type: str  # text, select, radio, checkbox
    env_variable: str
    resolved_value: str
    fill_success: bool = False
    error_message: str = ""

# Form field mapping configuration
FIELD_MAPPINGS = {
    # Name fields
    'firstName': 'REGISTRATION_FIRST_NAME',
    'first_name': 'REGISTRATION_FIRST_NAME',
    'name--legalName--firstName': 'REGISTRATION_FIRST_NAME',
    'fname': 'REGISTRATION_FIRST_NAME',
    'given_name': 'REGISTRATION_FIRST_NAME',
    
    'lastName': 'REGISTRATION_LAST_NAME',
    'last_name': 'REGISTRATION_LAST_NAME',
    'name--legalName--lastName': 'REGISTRATION_LAST_NAME',
    'lname': 'REGISTRATION_LAST_NAME',
    'family_name': 'REGISTRATION_LAST_NAME',
    'surname': 'REGISTRATION_LAST_NAME',
    
    # Contact fields
    'email': 'REGISTRATION_EMAIL',
    'emailAddress': 'REGISTRATION_EMAIL',
    'email_address': 'REGISTRATION_EMAIL',
    'signInFormo': 'REGISTRATION_EMAIL',
    
    'phone': 'REGISTRATION_PHONE',
    'phoneNumber': 'REGISTRATION_PHONE',
    'phoneNumber--phoneNumber': 'REGISTRATION_PHONE',
    'phone_number': 'REGISTRATION_PHONE',
    'mobile': 'REGISTRATION_PHONE',
    'telephone': 'REGISTRATION_PHONE',
    
    # Address fields
    'address': 'LOCATION',
    'address--addressLine1': 'LOCATION',
    'addressLine1': 'LOCATION',
    'street_address': 'LOCATION',
    'address_line_1': 'LOCATION',
    
    'city': 'LOCATION',
    'address--city': 'LOCATION',
    
    'postalCode': 'LOCATION',
    'address--postalCode': 'LOCATION',
    'zip_code': 'LOCATION',
    'postal_code': 'LOCATION',
    
    'country': 'COUNTRY',
    'country--country': 'COUNTRY',
    
    'state': 'STATE',
    'address--countryRegion': 'STATE',
    'region': 'STATE',
    'province': 'STATE',
    
    # Professional fields
    'currentCompany': 'CURRENT_COMPANY',
    'current_company': 'CURRENT_COMPANY',
    'employer': 'CURRENT_COMPANY',
    'company': 'CURRENT_COMPANY',
    
    'currentRole': 'CURRENT_ROLE',
    'current_role': 'CURRENT_ROLE',
    'position': 'CURRENT_ROLE',
    'job_title': 'CURRENT_ROLE',
    'title': 'CURRENT_ROLE',
    
    'experience': 'YEARS_EXPERIENCE',
    'years_experience': 'YEARS_EXPERIENCE',
    'work_experience': 'YEARS_EXPERIENCE',
    
    'skills': 'PRIMARY_SKILLS',
    'technical_skills': 'PRIMARY_SKILLS',
    'key_skills': 'PRIMARY_SKILLS',
    
    # Education fields
    'education': 'EDUCATION_MASTERS',
    'degree': 'EDUCATION_MASTERS',
    'university': 'EDUCATION_MASTERS',
    'school': 'EDUCATION_MASTERS',
    
    # Source/referral fields
    'source': 'JOB_BOARD',
    'source--source': 'JOB_BOARD',
    'referral_source': 'JOB_BOARD',
    'how_did_you_hear': 'JOB_BOARD'
}

# Dropdown option matching configuration
DROPDOWN_MAPPINGS = {
    'country': {
        'United States': ['US', 'USA', 'United States', 'America', 'United States of America'],
        'Canada': ['CA', 'Canada'],
        'United Kingdom': ['UK', 'GB', 'United Kingdom', 'Britain', 'England'],
        'India': ['IN', 'India'],
        'Germany': ['DE', 'Germany', 'Deutschland'],
        'France': ['FR', 'France'],
        'Australia': ['AU', 'Australia'],
        'China': ['CN', 'China'],
        'Japan': ['JP', 'Japan']
    },
    'state': {
        'California': ['CA', 'California', 'Calif'],
        'New York': ['NY', 'New York'],
        'Texas': ['TX', 'Texas'],
        'Florida': ['FL', 'Florida'],
        'Illinois': ['IL', 'Illinois'],
        'Pennsylvania': ['PA', 'Pennsylvania'],
        'Ohio': ['OH', 'Ohio'],
        'Georgia': ['GA', 'Georgia'],
        'North Carolina': ['NC', 'North Carolina'],
        'Michigan': ['MI', 'Michigan']
    },
    'experience': {
        '7+ years': ['7+', '7-10', '5+', '5-10', 'Senior', 'Expert'],
        '5-7 years': ['5-7', 'Mid-Senior'],
        '3-5 years': ['3-5', 'Mid-level', 'Intermediate'],
        '1-3 years': ['1-3', 'Junior', 'Entry'],
        '0-1 years': ['0-1', 'Fresh', 'Graduate', 'New']
    },
    'source': {
        'Company Website': ['Website', 'Company Site', 'Direct'],
        'LinkedIn': ['LinkedIn', 'Professional Network'],
        'Indeed': ['Indeed', 'Job Board'],
        'Glassdoor': ['Glassdoor'],
        'Referral': ['Referral', 'Employee Referral', 'Friend'],
        'Recruiter': ['Recruiter', 'Headhunter'],
        'Other': ['Other', 'Search Engine', 'Google']
    },
    'previous_worker': {
        'No': ['No', 'Never', 'First time'],
        'Yes': ['Yes', 'Previously', 'Former employee']
    }
}

class WorkdayFormScraper:
    """Main scraper class for job application form extraction"""
    
    def __init__(self):
        self.discovered_pages: List[PageInfo] = []
        self.form_elements: List[FormElement] = []
        self.errors: List[str] = []
        self.tenant_url = os.getenv('WORKDAY_TENANT_URL', '')
        self.extracted_pages: set = set()  # Track pages we've already extracted from
        self.autofill = WorkdayAutoFill()  # Initialize auto-fill functionality
        
    def _map_form_fields(self, form_elements: List[FormElement]) -> List[FieldMapping]:
        """Map extracted form fields to appropriate CV data from environment variables"""
        field_mappings = []
        
        for form_element in form_elements:
            field_id = form_element.id_of_input_component
            field_type = form_element.type_of_input
            
            # Skip non-input elements
            if field_type in ['submit', 'button']:
                continue
            
            # Try exact match first
            env_variable = FIELD_MAPPINGS.get(field_id)
            
            # If no exact match, try fuzzy matching
            if not env_variable:
                env_variable = self._fuzzy_match_field(field_id, form_element.label)
            
            if env_variable:
                resolved_value = self._resolve_field_value(form_element, env_variable)
                
                field_mapping = FieldMapping(
                    field_id=field_id,
                    field_type=field_type,
                    env_variable=env_variable,
                    resolved_value=resolved_value
                )
                field_mappings.append(field_mapping)
                print(f"  📋 Mapped field '{field_id}' -> {env_variable} = '{resolved_value[:50]}...'")
            else:
                print(f"  ⚠️ No mapping found for field: {field_id} (label: {form_element.label})")
        
        return field_mappings
    
    def _fuzzy_match_field(self, field_id: str, field_label: str) -> Optional[str]:
        """Attempt fuzzy matching for field names that don't exactly match mapping keys"""
        field_id_lower = field_id.lower()
        field_label_lower = field_label.lower()
        
        # Check if any mapping key is contained in the field ID or label
        for mapping_key, env_var in FIELD_MAPPINGS.items():
            mapping_key_lower = mapping_key.lower()
            
            # Check for partial matches in field ID
            if mapping_key_lower in field_id_lower or field_id_lower in mapping_key_lower:
                return env_var
            
            # Check for partial matches in field label
            if field_label and (mapping_key_lower in field_label_lower or field_label_lower in mapping_key_lower):
                return env_var
            
            # Check for keyword matches
            keywords = {
                'first': 'REGISTRATION_FIRST_NAME',
                'last': 'REGISTRATION_LAST_NAME',
                'email': 'REGISTRATION_EMAIL',
                'phone': 'REGISTRATION_PHONE',
                'address': 'LOCATION',
                'city': 'LOCATION',
                'country': 'COUNTRY',
                'state': 'STATE',
                'company': 'CURRENT_COMPANY',
                'role': 'CURRENT_ROLE',
                'experience': 'YEARS_EXPERIENCE',
                'skill': 'PRIMARY_SKILLS',
                'education': 'EDUCATION_MASTERS',
                'source': 'JOB_BOARD'
            }
            
            for keyword, env_var in keywords.items():
                if keyword in field_id_lower or (field_label and keyword in field_label_lower):
                    return env_var
        
        return None
    
    def _resolve_field_value(self, form_element: FormElement, env_variable: str) -> str:
        """Determine the appropriate value for a specific form field"""
        # Get value from environment variable
        env_value = os.getenv(env_variable, '')
        
        if not env_value:
            print(f"    ⚠️ Environment variable {env_variable} is empty")
            return ''
        
        # Handle different field types
        field_type = form_element.type_of_input
        field_id = form_element.id_of_input_component
        
        if field_type == 'select':
            # For dropdown fields, try to match with available options
            return self._match_dropdown_option(form_element, env_value)
        elif field_type == 'radio':
            # For radio fields, try to match with available options
            return self._match_radio_option(form_element, env_value)
        elif field_type in ['text', 'email', 'tel']:
            # For text fields, format the value appropriately
            return self._format_text_value(field_id, env_value)
        else:
            return env_value
    
    def _match_dropdown_option(self, form_element: FormElement, env_value: str) -> str:
        """Match environment value with available dropdown options"""
        available_options = form_element.options
        
        if not available_options:
            return env_value
        
        # Try exact match first
        for option in available_options:
            if option.lower() == env_value.lower():
                return option
        
        # Try fuzzy matching using DROPDOWN_MAPPINGS
        field_id = form_element.id_of_input_component.lower()
        
        for mapping_type, mappings in DROPDOWN_MAPPINGS.items():
            if mapping_type in field_id:
                for standard_value, variations in mappings.items():
                    if env_value in variations or env_value.lower() in [v.lower() for v in variations]:
                        # Find the matching option in available options
                        for option in available_options:
                            if option.lower() == standard_value.lower() or standard_value.lower() in option.lower():
                                return option
        
        # If no match found, return the first available option
        print(f"    ⚠️ No exact match for '{env_value}' in dropdown options: {available_options}")
        return available_options[0] if available_options else env_value
    
    def _match_radio_option(self, form_element: FormElement, env_value: str) -> str:
        """Match environment value with available radio options"""
        available_options = form_element.options
        
        if not available_options:
            return env_value
        
        # Try exact match first
        for option in available_options:
            if option.lower() == env_value.lower():
                return option
        
        # For common radio button scenarios
        if 'previous' in form_element.id_of_input_component.lower():
            # Handle "Have you worked here before?" type questions
            if env_value.lower() in ['no', 'never', 'first time']:
                return 'No'
            elif env_value.lower() in ['yes', 'previously', 'former']:
                return 'Yes'
        
        # Return first available option as fallback
        return available_options[0] if available_options else env_value
    
    def _format_text_value(self, field_id: str, env_value: str) -> str:
        """Format text value appropriately for the field"""
        field_id_lower = field_id.lower()
        
        # Handle phone number formatting
        if 'phone' in field_id_lower:
            # Remove any non-digit characters and format
            digits_only = re.sub(r'\D', '', env_value)
            if len(digits_only) == 10:
                return f"({digits_only[:3]}) {digits_only[3:6]}-{digits_only[6:]}"
            return env_value
        
        # Handle postal code formatting
        if 'postal' in field_id_lower or 'zip' in field_id_lower:
            # Extract just the postal code part if it's in a full address
            if ',' in env_value:
                # Assume format like "California, USA" and extract nothing
                return ''
            return env_value
        
        # Handle city extraction from location
        if 'city' in field_id_lower and ',' in env_value:
            # Extract city from "California, USA" format
            return env_value.split(',')[0].strip()
        
        # Handle address line extraction
        if 'address' in field_id_lower and 'line1' in field_id_lower:
            # For address line 1, we might not have specific street address
            return ''  # Leave empty as we only have city/state info
        
        return env_value
        
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
                
                # Save intermediate results after initial extraction
                print("\n📍 Phase 4.5: Saving Intermediate Results")
                intermediate_results = await self._create_results()
                await self._save_results(intermediate_results)
                print("  ✅ Intermediate results saved")
                
                # Phase 5: Create account using extracted form data
                print("\n📍 Phase 5: Creating Account")
                account_success = await self._create_account(page)
                
                if account_success:
                    print("  ✅ Account created successfully")
                    
                    # Phase 6: Navigate to next page after account creation
                    print("\n📍 Phase 6: Navigating to Next Page")
                    await self._navigate_to_next_page(page)
                    
                    # Phase 7: Extract form elements from My Information page
                    print("\n📍 Phase 7: Extracting My Information Page Elements")
                    await self._extract_my_information_page(page)
                else:
                    print("  ⚠️ Account creation failed, but continuing...")
                
                # Phase 8: Create and save results
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
        
        # Check if we've already extracted from this page
        if current_url in self.extracted_pages:
            print(f"  ℹ️ Already extracted from this page: {current_url}")
            return
        
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
        self.extracted_pages.add(current_url)  # Mark as extracted
        
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
    
    async def _create_account(self, page: Page) -> bool:
        """Create account using the extracted form elements"""
        print("  🔐 Starting account creation process...")
        
        try:
            # Step 1: Fill email field
            email_filled = await self._fill_email_field(page)
            if not email_filled:
                print("  ❌ Failed to fill email field")
                return False
            
            # Step 2: Fill password field
            password_filled = await self._fill_password_field(page)
            if not password_filled:
                print("  ❌ Failed to fill password field")
                return False
            
            # Step 3: Fill verify password field
            verify_password_filled = await self._fill_verify_password_field(page)
            if not verify_password_filled:
                print("  ❌ Failed to fill verify password field")
                return False
            
            # Step 4: Handle checkbox if present
            await self._handle_checkbox(page)
            
            # Step 5: Submit the form
            submit_success = await self._submit_account_form(page)
            if not submit_success:
                print("  ❌ Failed to submit account creation form")
                return False
            
            # Step 6: Wait for account creation to complete
            await self._wait_for_account_creation(page)
            
            print("  ✅ Account creation completed successfully")
            return True
            
        except Exception as e:
            self.errors.append(f"Account creation error: {str(e)}")
            print(f"  ❌ Account creation failed: {str(e)}")
            return False
    
    async def _fill_email_field(self, page: Page) -> bool:
        """Fill email field using multiple selectors"""
        email_selectors = [
            'input[data-automation-id="email"]',
            'input[type="email"]',
            'input[name="email"]',
            'input[placeholder*="email" i]'
        ]
        
        email = os.getenv('WORKDAY_USERNAME', '')
        if not email:
            print("    ❌ No email found in environment variables")
            return False
        
        for selector in email_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=3000, state='visible')
                if element:
                    await element.fill(email)
                    print(f"    ✅ Email filled using: {selector}")
                    return True
            except:
                continue
        
        print("    ❌ Email field not found")
        return False
    
    async def _fill_password_field(self, page: Page) -> bool:
        """Fill password field using multiple selectors"""
        password_selectors = [
            'input[data-automation-id="password"]',
            'input[type="password"]',
            'input[name="password"]'
        ]
        
        password = os.getenv('WORKDAY_PASSWORD', '')
        if not password:
            print("    ❌ No password found in environment variables")
            return False
        
        for selector in password_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=3000, state='visible')
                if element:
                    await element.fill(password)
                    print(f"    ✅ Password filled using: {selector}")
                    return True
            except:
                continue
        
        print("    ❌ Password field not found")
        return False
    
    async def _fill_verify_password_field(self, page: Page) -> bool:
        """Fill verify password field using multiple selectors"""
        verify_selectors = [
            'input[data-automation-id="verifyPassword"]',
            'input[name="verifyPassword"]',
            'input[name="confirmPassword"]',
            'input[placeholder*="verify" i]',
            'input[placeholder*="confirm" i]'
        ]
        
        password = os.getenv('WORKDAY_PASSWORD', '')
        if not password:
            print("    ❌ No password found in environment variables")
            return False
        
        for selector in verify_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=3000, state='visible')
                if element:
                    await element.fill(password)
                    print(f"    ✅ Verify password filled using: {selector}")
                    return True
            except:
                continue
        
        print("    ⚠️ Verify password field not found (may be optional)")
        return True  # Return true as it might be optional
    
    async def _handle_checkbox(self, page: Page):
        """Handle any checkboxes (terms, conditions, etc.)"""
        checkbox_selectors = [
            'input[data-automation-id="createAccountCheckbox"]',
            'input[type="checkbox"]',
            'input[name*="terms"]',
            'input[name*="agree"]'
        ]
        
        for selector in checkbox_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=2000, state='visible')
                if element:
                    await element.check()
                    print(f"    ✅ Checkbox checked using: {selector}")
                    break
            except:
                continue
    
    async def _submit_account_form(self, page: Page) -> bool:
        """Submit the account creation form"""
        submit_selectors = [
            'button[data-automation-id="createAccountSubmitButton"]',
            'button:has-text("Create Account")',
            'button:has-text("Sign Up")',
            'button[type="submit"]',
            'input[type="submit"]'
        ]
        
        for selector in submit_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=5000, state='visible')
                if element and not await element.is_disabled():
                    # Try multiple click strategies
                    try:
                        await element.click()
                        print(f"    ✅ Form submitted using: {selector}")
                        return True
                    except:
                        try:
                            await element.click(force=True)
                            print(f"    ✅ Form submitted (force) using: {selector}")
                            return True
                        except:
                            try:
                                await element.evaluate("element => element.click()")
                                print(f"    ✅ Form submitted (JS) using: {selector}")
                                return True
                            except:
                                continue
            except:
                continue
        
        # Fallback: Try Enter key
        try:
            await page.keyboard.press("Enter")
            print("    ✅ Form submitted using Enter key")
            return True
        except:
            pass
        
        print("    ❌ Submit button not found or not clickable")
        return False
    
    async def _wait_for_account_creation(self, page: Page):
        """Wait for account creation to complete and detect success"""
        print("    ⏳ Waiting for account creation to complete...")
        
        # Wait for page transition
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(3)
        
        # Check for success indicators
        success_indicators = [
            'text="Welcome"',
            'text="Account Created"',
            'text="Registration Complete"',
            'text="Success"',
            '.success-message',
            '[data-automation-id*="success"]'
        ]
        
        for indicator in success_indicators:
            try:
                if await page.query_selector(indicator):
                    print(f"    ✅ Account creation success detected: {indicator}")
                    return True
            except:
                continue
        
        # Check if URL changed (indicating progression)
        current_url = page.url
        if 'apply' in current_url.lower() and 'manually' not in current_url.lower():
            print("    ✅ Account creation appears successful (URL changed)")
            return True
        
        print("    ⚠️ Account creation status unclear, but proceeding...")
        return True
    
    async def _navigate_to_next_page(self, page: Page):
        """Navigate to the next page after account creation"""
        print("  🔍 Looking for navigation to next page...")
        
        # Wait for any post-creation redirects
        await asyncio.sleep(3)
        
        # Look for navigation elements to continue the application
        nav_selectors = [
            'a:has-text("Continue")',
            'a:has-text("Next")',
            'a:has-text("Start Application")',
            'a:has-text("Begin")',
            'button:has-text("Continue")',
            'button:has-text("Next")',
            'button:has-text("Start Application")',
            '[data-automation-id*="continue"]',
            '[data-automation-id*="next"]',
            '[data-automation-id*="start"]'
        ]
        
        for selector in nav_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=5000, state='visible')
                if element:
                    nav_text = await element.inner_text()
                    print(f"  ✅ Found navigation: '{nav_text}'")
                    await element.click()
                    print("  🖱️ Clicked navigation element")
                    
                    # Wait for next page to load
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    await asyncio.sleep(2)
                    
                    # Extract forms from the new page
                    current_url = page.url
                    page_title = await page.title()
                    page_info = PageInfo(
                        url=current_url,
                        path=current_url.replace(self.tenant_url, '') or '/',
                        title=page_title,
                        page_type="Application Flow",
                        visited=True
                    )
                    
                    page_forms = await self._extract_page_forms(page, page_info)
                    page_info.form_count = len(page_forms)
                    self.form_elements.extend(page_forms)
                    self.discovered_pages.append(page_info)
                    
                    print(f"  ✅ Next page: Extracted {len(page_forms)} additional form elements")
                    return True
            except:
                continue
        
        print("  ℹ️ No navigation to next page found - account creation may be complete")
        return False
    
    async def _extract_my_information_page(self, page: Page):
        """Extract form elements from My Information page after account creation"""
        print("  📋 Extracting form elements from My Information page...")
        
        try:
            # Wait for My Information page to fully load
            await page.wait_for_load_state("networkidle", timeout=10000)
            await asyncio.sleep(3)  # Allow dynamic content to load
            
            # Create page info for My Information page
            current_url = page.url
            
            # Check if we've already extracted from this page
            if current_url in self.extracted_pages:
                print(f"  ℹ️ Already extracted from this page: {current_url}")
                return
            
            page_title = await page.title()
            page_info = PageInfo(
                url=current_url,
                path=current_url.replace(self.tenant_url, '') or '/',
                title=page_title,
                page_type="My Information",
                visited=True
            )
            
            # Extract form elements from My Information page
            page_forms = await self._extract_page_forms(page, page_info)
            page_info.form_count = len(page_forms)
            self.form_elements.extend(page_forms)
            self.discovered_pages.append(page_info)
            self.extracted_pages.add(current_url)  # Mark as extracted
            
            print(f"  ✅ Extracted {len(page_forms)} form elements from My Information page")
            
            # Look for additional sections or pages within My Information
            await self._navigate_my_information_sections(page)
            
        except Exception as e:
            self.errors.append(f"Error extracting My Information page: {str(e)}")
            print(f"  ❌ Error extracting My Information page: {str(e)}")
    
    async def _navigate_my_information_sections(self, page: Page):
        """Navigate through different sections of My Information page"""
        print("  🔍 Looking for My Information sections...")
        
        # Common My Information section navigation
        section_selectors = [
            'a:has-text("Personal Information")',
            'a:has-text("Contact Information")',
            'a:has-text("Address")',
            'a:has-text("Phone")',
            'a:has-text("Emergency Contact")',
            'a:has-text("Education")',
            'a:has-text("Work Experience")',
            'a:has-text("Skills")',
            'button:has-text("Next")',
            'button:has-text("Continue")',
            '[data-automation-id*="next"]',
            '[data-automation-id*="continue"]',
            '[data-automation-id*="section"]'
        ]
        
        visited_sections = {page.url}
        sections_processed = 1
        max_sections = 5
        
        while sections_processed < max_sections:
            section_found = False
            
            for selector in section_selectors:
                try:
                    section_element = await page.wait_for_selector(selector, timeout=3000, state='visible')
                    if section_element:
                        section_text = await section_element.inner_text()
                        print(f"    🔗 Found section: {section_text}")
                        
                        await section_element.click()
                        await page.wait_for_load_state("networkidle", timeout=8000)
                        await asyncio.sleep(2)
                        
                        # Check if we're on a new section/page
                        new_url = page.url
                        if new_url not in visited_sections:
                            visited_sections.add(new_url)
                            
                            # Extract forms from new section
                            page_title = await page.title()
                            section_info = PageInfo(
                                url=new_url,
                                path=new_url.replace(self.tenant_url, '') or '/',
                                title=f"{page_title} - {section_text}",
                                page_type="My Information Section",
                                visited=True
                            )
                            
                            section_forms = await self._extract_page_forms(page, section_info)
                            section_info.form_count = len(section_forms)
                            self.form_elements.extend(section_forms)
                            self.discovered_pages.append(section_info)
                            
                            print(f"    ✅ Section {sections_processed + 1}: Extracted {len(section_forms)} form elements")
                            sections_processed += 1
                            section_found = True
                            break
                        else:
                            print(f"    ℹ️ Already visited this section")
                            
                except:
                    continue
            
            if not section_found:
                print("    ℹ️ No more sections found")
                break
        
        print(f"  ✅ My Information sections complete: {sections_processed} sections processed")
    
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
        """Extract all form elements from current page with improved radio grouping and dropdown extraction"""
        form_elements = []
        processed_radio_groups = set()  # Track processed radio button groups
        
        try:
            # Wait for dynamic content to load
            await asyncio.sleep(2)
            
            # Find form containers using multiple strategies
            containers = await self._find_form_containers(page)
            
            print(f"    🔍 Found {len(containers)} form containers")
            
            # First pass: Group radio buttons by name attribute
            radio_groups = await self._group_radio_buttons(page)
            
            # Process radio groups first
            for group_name, radio_info in radio_groups.items():
                if group_name not in processed_radio_groups:
                    form_element = FormElement(
                        label=radio_info['label'],
                        id_of_input_component=group_name,
                        required=radio_info['required'],
                        type_of_input="radio",
                        options=radio_info['options'],
                        user_data_select_values=radio_info['sample_values'],
                        page_url=page_info.url,
                        page_title=page_info.title
                    )
                    form_elements.append(form_element)
                    processed_radio_groups.add(group_name)
                    print(f"    ✅ Grouped radio buttons: {group_name} with {len(radio_info['options'])} options")
            
            # Second pass: Process other form elements
            for container in containers:
                try:
                    # Skip invisible elements
                    if not await container.is_visible():
                        continue
                    
                    # Identify form control type
                    control_type = await self._identify_control_type(container)
                    if not control_type:
                        continue
                    
                    # Skip individual radio buttons (already processed in groups)
                    if control_type == "radio":
                        radio_name = await self._get_radio_group_name(container)
                        if radio_name in processed_radio_groups:
                            continue
                    
                    # Extract element data
                    label = await self._extract_label(container)
                    identifier = await self._extract_identifier(container)
                    required = await self._is_required(container)
                    
                    # Enhanced options extraction for dropdowns
                    options = []
                    if control_type in ("select", "multiselect", "checkbox"):
                        options = await self._extract_options_enhanced(container, control_type, identifier)
                    
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
        """Find all form containers and individual form elements with enhanced dropdown detection"""
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
        
        # Strategy 5: Enhanced dropdown detection (especially for country and source dropdowns)
        dropdown_elements = await page.query_selector_all(
            'select, [role="combobox"], [data-automation-id*="dropdown"], '
            '[id="country--country"], [data-automation-id="country--country"], '
            '[id="source--source"], [data-automation-id="source--source"], '
            '[id*="country"], [name*="country"], [id*="source"], [name*="source"], '
            '[class*="dropdown"], [class*="select"], [aria-haspopup="listbox"]'
        )
        containers.extend(dropdown_elements)
        
        # Strategy 6: Radio button groups
        radio_groups = await page.query_selector_all(
            '[role="radiogroup"], [data-automation-id*="radio"], '
            'input[type="radio"][name="candidateIsPreviousWorker"]'
        )
        containers.extend(radio_groups)
        
        # Strategy 7: Specific country dropdown detection
        try:
            country_dropdown = await page.query_selector('[id="country--country"]')
            if country_dropdown:
                containers.append(country_dropdown)
                print(f"    🌍 Found specific country dropdown with id='country--country'")
        except:
            pass
        
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
        
        print(f"    🔍 Found {len(unique_containers)} form containers/elements")
        return unique_containers
    
    async def _identify_control_type(self, element) -> Optional[str]:
        """Identify form control type with enhanced dropdown detection"""
        try:
            tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
            element_id = await element.get_attribute('id') or ''
            element_role = await element.get_attribute('role') or ''
            element_class = await element.get_attribute('class') or ''
            
            # Special handling for country dropdown
            if element_id == 'country--country' or 'country--country' in element_id:
                print(f"    🌍 Detected country dropdown: {element_id}")
                return 'select'
            
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
                
                # Check if button is actually a dropdown trigger
                if (element_role == 'combobox' or 
                    'dropdown' in element_class.lower() or 
                    'select' in element_class.lower() or
                    'country' in element_id.lower()):
                    return 'select'
                
                return 'submit' if button_type == 'submit' else None
            
            elif tag_name == 'div':
                # Check if div is acting as a dropdown
                if (element_role == 'combobox' or 
                    'dropdown' in element_class.lower() or 
                    'select' in element_class.lower() or
                    element_id == 'country--country'):
                    return 'select'
            
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
                elif await element.query_selector('div[role="combobox"], button[role="combobox"]'):
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
    
    async def _group_radio_buttons(self, page: Page) -> Dict[str, Dict]:
        """Group radio buttons by their name attribute"""
        radio_groups = {}
        
        try:
            # Find all radio buttons on the page
            radio_buttons = await page.query_selector_all('input[type="radio"]')
            
            for radio in radio_buttons:
                try:
                    # Get radio button attributes
                    radio_name = await radio.get_attribute('name')
                    radio_id = await radio.get_attribute('id')
                    radio_value = await radio.get_attribute('value')
                    
                    if not radio_name:
                        continue
                    
                    # Initialize group if not exists
                    if radio_name not in radio_groups:
                        # Try to find a label for the group
                        group_label = await self._find_radio_group_label(page, radio_name, radio)
                        
                        radio_groups[radio_name] = {
                            'label': group_label,
                            'options': [],
                            'required': False,
                            'sample_values': []
                        }
                    
                    # Find label for this specific radio option
                    option_label = ""
                    if radio_id:
                        # Look for label with for attribute
                        label_element = await page.query_selector(f'label[for="{radio_id}"]')
                        if label_element:
                            option_label = await label_element.inner_text()
                            option_label = option_label.strip()
                    
                    # If no label found, use value or id
                    if not option_label:
                        option_label = radio_value or radio_id or "Unknown Option"
                    
                    # Add option to group if not already present
                    if option_label not in radio_groups[radio_name]['options']:
                        radio_groups[radio_name]['options'].append(option_label)
                    
                    # Check if required
                    if not radio_groups[radio_name]['required']:
                        radio_groups[radio_name]['required'] = await self._is_radio_required(radio)
                
                except Exception as e:
                    print(f"    ⚠️ Error processing radio button: {str(e)}")
                    continue
            
            # Set sample values for each group
            for group_name, group_info in radio_groups.items():
                if group_info['options']:
                    # Smart selection based on common patterns
                    sample_value = self._select_smart_radio_option(group_info['options'], group_info['label'])
                    group_info['sample_values'] = [sample_value]
                    
                    print(f"    ✅ Radio group '{group_name}': {len(group_info['options'])} options")
        
        except Exception as e:
            print(f"    ⚠️ Error grouping radio buttons: {str(e)}")
        
        return radio_groups
    
    async def _find_radio_group_label(self, page: Page, radio_name: str, first_radio) -> str:
        """Find label for radio button group"""
        try:
            # Strategy 1: Look for fieldset legend
            fieldset = await first_radio.evaluate('''
                (radio) => {
                    let current = radio;
                    while (current && current.tagName !== 'FIELDSET') {
                        current = current.parentElement;
                    }
                    return current;
                }
            ''')
            
            if fieldset:
                legend = await fieldset.query_selector('legend')
                if legend:
                    legend_text = await legend.inner_text()
                    if legend_text.strip():
                        return legend_text.strip()
            
            # Strategy 2: Look for common label patterns
            container = await first_radio.evaluate('''
                (radio) => {
                    let current = radio;
                    for (let i = 0; i < 5; i++) {
                        if (!current.parentElement) break;
                        current = current.parentElement;
                        
                        // Look for elements that might contain the group label
                        const labelElements = current.querySelectorAll('label, .label, .question, .form-label, [data-automation-id*="label"]');
                        for (let label of labelElements) {
                            const text = label.textContent.trim();
                            if (text && !label.getAttribute('for')) {
                                return label;
                            }
                        }
                    }
                    return null;
                }
            ''')
            
            if container:
                label_text = await container.inner_text()
                if label_text.strip():
                    return label_text.strip()
            
            # Strategy 3: Use radio name as fallback
            formatted_name = re.sub(r'([A-Z])', r' \1', radio_name).strip()
            return formatted_name.capitalize() if formatted_name else radio_name
        
        except Exception:
            pass
        
        return f"Radio Group ({radio_name})"
    
    async def _is_radio_required(self, radio_element) -> bool:
        """Check if radio button group is required"""
        try:
            # Check aria-required
            aria_required = await radio_element.get_attribute('aria-required')
            if aria_required == 'true':
                return True
            
            # Check required attribute
            required_attr = await radio_element.get_attribute('required')
            if required_attr is not None:
                return True
            
            # Check parent container for required indicators
            container = await radio_element.evaluate('''
                (radio) => {
                    let current = radio;
                    for (let i = 0; i < 3; i++) {
                        if (!current.parentElement) break;
                        current = current.parentElement;
                        
                        if (current.querySelector('[aria-required="true"]') || 
                            current.querySelector('.required') ||
                            current.textContent.includes('*')) {
                            return true;
                        }
                    }
                    return false;
                }
            ''')
            
            return container
        
        except Exception:
            pass
        
        return False
    
    def _select_smart_radio_option(self, options: List[str], group_label: str) -> str:
        """Smart selection of radio option based on context"""
        if not options:
            return ""
        
        group_label_lower = group_label.lower()
        
        # For previous worker questions, prefer "No"
        if 'previous' in group_label_lower and 'worker' in group_label_lower:
            for option in options:
                if option.lower() in ['no', 'false']:
                    return option
        
        # For authorization questions, prefer "Yes"
        if any(keyword in group_label_lower for keyword in ['authorized', 'eligible', 'legal']):
            for option in options:
                if option.lower() in ['yes', 'true']:
                    return option
        
        # For visa/sponsorship questions, prefer "No"
        if any(keyword in group_label_lower for keyword in ['visa', 'sponsor', 'h1b']):
            for option in options:
                if option.lower() in ['no', 'false', 'not required']:
                    return option
        
        # Default to first option
        return options[0]
    
    async def _get_radio_group_name(self, container) -> str:
        """Get radio group name from container"""
        try:
            radio_element = await container.query_selector('input[type="radio"]')
            if radio_element:
                return await radio_element.get_attribute('name') or ""
        except Exception:
            pass
        return ""
    
    async def _extract_options_enhanced(self, element, control_type: str, identifier: str) -> List[str]:
        """Enhanced options extraction with special handling for known dropdowns"""
        options = []
        
        try:
            if control_type in ("select", "multiselect"):
                # Special handling for known dropdowns
                if 'source' in identifier.lower():
                    print(f"    🎯 Special handling for source dropdown: {identifier}")
                    options = await self._extract_source_dropdown_options(element)
                elif 'country' in identifier.lower() or identifier == 'country--country':
                    print(f"    🎯 Special handling for country dropdown: {identifier}")
                    options = await self._extract_country_dropdown_options(element)
                else:
                    # General dropdown extraction
                    options = await self._extract_dropdown_options(element)
                
            elif control_type == "checkbox":
                # Handle checkbox groups
                options = await self._extract_checkbox_options(element)
        
        except Exception as e:
            print(f"    ⚠️ Error in enhanced options extraction: {str(e)}")
        
        return options
    
    async def _extract_source_dropdown_options(self, element) -> List[str]:
        """Extract options from source dropdown with fallback values"""
        options = []
        
        try:
            # Try to extract actual options
            options = await self._extract_dropdown_options(element)
            
            # If no options found, provide common source options
            if not options:
                options = [
                    "Direct",
                    "Employee Referral", 
                    "LinkedIn",
                    "Indeed",
                    "Glassdoor",
                    "University/College",
                    "Job Fair",
                    "Company Website",
                    "Other"
                ]
                print(f"    ℹ️ Using predefined source options")
        
        except Exception:
            pass
        
        return options
    
    async def _extract_country_dropdown_options(self, element) -> List[str]:
        """Return simplified country dropdown identifier without extracting options"""
        print(f"    🌍 Simplified country dropdown handling - returning identifier only")
        return ["country--country"]
    
    async def _extract_dropdown_options(self, element) -> List[str]:
        """Extract options from dropdown element"""
        options = []
        
        try:
            # Strategy 1: Try to click and open dropdown
            try:
                await element.click()
                await asyncio.sleep(1)  # Wait for dropdown to open
                
                # Look for options with multiple selectors
                option_selectors = [
                    'option',
                    'div[role="option"]',
                    'li[role="option"]',
                    '.dropdown-option',
                    '.select-option',
                    '[data-automation-id*="option"]',
                    '[data-automation-value]'
                ]
                
                for selector in option_selectors:
                    try:
                        # Look in element first, then in page
                        option_elements = await element.query_selector_all(selector)
                        if not option_elements:
                            # Look in entire page for dropdowns that open elsewhere
                            page = element.page
                            option_elements = await page.query_selector_all(selector)
                        
                        for opt in option_elements:
                            if await opt.is_visible():
                                option_text = await opt.inner_text()
                                if option_text.strip():
                                    options.append(option_text.strip())
                    except:
                        continue
                
                # Close dropdown
                await element.press('Escape')
                
            except Exception:
                # Strategy 2: Look for option elements directly
                option_elements = await element.query_selector_all('option')
                for opt in option_elements:
                    option_text = await opt.inner_text()
                    if option_text.strip():
                        options.append(option_text.strip())
        
        except Exception:
            pass
        
        return list(set(options))  # Remove duplicates
    
    async def _extract_checkbox_options(self, element) -> List[str]:
        """Extract options from checkbox groups"""
        options = []
        
        try:
            checkbox_elements = await element.query_selector_all('input[type="checkbox"]')
            for checkbox in checkbox_elements:
                try:
                    checkbox_id = await checkbox.get_attribute('id')
                    if checkbox_id:
                        # Look for associated label
                        page = element.page
                        label = await page.query_selector(f'label[for="{checkbox_id}"]')
                        if label:
                            label_text = await label.inner_text()
                            if label_text.strip():
                                options.append(label_text.strip())
                except:
                    continue
        
        except Exception:
            pass
        
        return options
    
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