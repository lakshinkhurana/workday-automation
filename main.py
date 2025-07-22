#!/usr/bin/env python3
"""
Workday Form Scraper with Authentication State
Author: Web Automation Engineer
Date: 2023-11-15
Description: 
Automates login, navigation, and form extraction from Workday portals.
Saves authentication state to avoid repeated logins.
"""

import os
import json
import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import List, Optional
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Load environment variables from .env file
load_dotenv()

# Configuration constants
DEFAULT_START_PATH = "/myaccount/home"
AUTH_STATE_FILE = "workday_auth_state.json"
OUTPUT_FILE = "workday_forms.json"

def get_target_url():
    """Get the target URL for form extraction - prioritize JOB_URL if available"""
    job_url = os.getenv('JOB_URL')
    if job_url:
        return job_url
    else:
        return os.getenv('WORKDAY_TENANT_URL') + DEFAULT_START_PATH

@dataclass
class RegistrationConfig:
    """
    Configuration class for handling registration environment variables and validation.
    Manages all registration-related settings and provides validation for required fields.
    """
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    create_account_mode: bool = False
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        self.first_name = os.getenv('REGISTRATION_FIRST_NAME', '').strip()
        self.last_name = os.getenv('REGISTRATION_LAST_NAME', '').strip()
        self.email = os.getenv('REGISTRATION_EMAIL', '').strip()
        self.password = os.getenv('REGISTRATION_PASSWORD', '').strip()
        self.phone = os.getenv('REGISTRATION_PHONE', '').strip()
        self.create_account_mode = os.getenv('CREATE_ACCOUNT_MODE', 'false').lower() == 'true'
    
    def validate_required_fields(self) -> List[str]:
        """
        Validates required registration fields when CREATE_ACCOUNT_MODE is enabled.
        
        Returns:
            List[str]: List of missing required field names. Empty list if all required fields are present.
        """
        missing_fields = []
        
        # Only validate if create account mode is enabled
        if not self.create_account_mode:
            return missing_fields
        
        # Check required fields
        required_fields = {
            'REGISTRATION_FIRST_NAME': self.first_name,
            'REGISTRATION_LAST_NAME': self.last_name,
            'REGISTRATION_EMAIL': self.email,
            'REGISTRATION_PASSWORD': self.password
        }
        
        for field_name, field_value in required_fields.items():
            if not field_value:
                missing_fields.append(field_name)
        
        return missing_fields
    
    def validate_configuration(self) -> None:
        """
        Validates the registration configuration and raises appropriate errors.
        
        Raises:
            ValueError: If required fields are missing when CREATE_ACCOUNT_MODE is enabled.
            RuntimeError: If configuration validation fails for other reasons.
        """
        try:
            missing_fields = self.validate_required_fields()
            
            if missing_fields:
                error_msg = (
                    f"❌ Registration configuration error: Missing required environment variables when CREATE_ACCOUNT_MODE=true:\n"
                    f"   Missing fields: {', '.join(missing_fields)}\n"
                    f"   Please set these environment variables in your .env file:\n"
                )
                for field in missing_fields:
                    error_msg += f"   {field}=your_value_here\n"
                
                raise ValueError(error_msg)
            
            # Additional validation for email format (basic check)
            if self.create_account_mode and self.email and '@' not in self.email:
                raise ValueError("❌ Registration configuration error: REGISTRATION_EMAIL must be a valid email address")
            
            # Additional validation for password strength (basic check)
            if self.create_account_mode and self.password and len(self.password) < 8:
                raise ValueError("❌ Registration configuration error: REGISTRATION_PASSWORD must be at least 8 characters long")
                
        except ValueError:
            # Re-raise ValueError as-is
            raise
        except Exception as e:
            # Wrap other exceptions in RuntimeError
            raise RuntimeError(f"❌ Registration configuration validation failed: {str(e)}")
    
    def is_registration_mode(self) -> bool:
        """
        Check if the system is configured for account registration mode.
        
        Returns:
            bool: True if CREATE_ACCOUNT_MODE is enabled, False otherwise.
        """
        return self.create_account_mode
    
    def get_registration_summary(self) -> str:
        """
        Get a summary of the current registration configuration for logging.
        
        Returns:
            str: Summary string with configuration details (passwords masked).
        """
        if not self.create_account_mode:
            return "Registration mode: DISABLED"
        
        return (
            f"Registration mode: ENABLED\n"
            f"  First Name: {self.first_name or 'NOT SET'}\n"
            f"  Last Name: {self.last_name or 'NOT SET'}\n"
            f"  Email: {self.email or 'NOT SET'}\n"
            f"  Password: {'*' * len(self.password) if self.password else 'NOT SET'}\n"
            f"  Phone: {self.phone or 'NOT SET (optional)'}"
        )

@dataclass
class RegistrationState:
    """
    Tracks the state of the registration process for debugging and recovery.
    """
    registration_started: bool = False
    form_filled: bool = False
    verification_pending: bool = False
    account_created: bool = False
    login_successful: bool = False

async def create_nvidia_account(page, config):
    """
    Main orchestration function that coordinates the entire registration process.
    
    Args:
        page: Playwright page object
        config: RegistrationConfig object with user data
        
    Returns:
        bool: True if account creation was successful, False otherwise
        
    Raises:
        Exception: If registration fails at any step
    """
    print("🚀 Starting NVIDIA account creation process...")
    
    # Initialize registration state tracking
    state = RegistrationState()
    
    try:
        # Step 1: Navigate to registration page
        print("\n📍 Step 1: Navigating to registration page")
        state.registration_started = True
        
        navigation_success = await navigate_to_registration(page)
        if not navigation_success:
            raise Exception("Failed to navigate to registration page")
        
        print("  ✅ Successfully navigated to registration page")
        
        # Step 2: Fill registration form
        print("\n📍 Step 2: Filling registration form")
        
        form_success = await fill_registration_form(page, config)
        if not form_success:
            raise Exception("Failed to fill registration form")
        
        state.form_filled = True
        print("  ✅ Registration form filled successfully")
        
        # Step 3: Submit the form
        print("\n📍 Step 3: Submitting registration form")
        
        submit_success = await submit_registration_form(page)
        if not submit_success:
            raise Exception("Failed to submit registration form")
        
        print("  ✅ Registration form submitted")
        
        # Step 4: Handle verification steps
        print("\n📍 Step 4: Handling verification steps")
        state.verification_pending = True
        
        verification_success = await handle_verification_steps(page)
        if not verification_success:
            print("  ⚠️ Verification steps incomplete - may require manual intervention")
            return False
        
        state.account_created = True
        print("  ✅ Account verification completed")
        
        # Step 5: Verify successful login/account creation
        print("\n📍 Step 5: Verifying account creation success")
        
        login_verification = await verify_account_creation_success(page)
        if login_verification:
            state.login_successful = True
            print("  ✅ Account creation and login verification successful")
        else:
            print("  ⚠️ Account created but login verification incomplete")
        
        # Log final state
        print(f"\n🎯 Registration process completed!")
        print(f"  Registration State Summary:")
        print(f"    Started: {state.registration_started}")
        print(f"    Form Filled: {state.form_filled}")
        print(f"    Account Created: {state.account_created}")
        print(f"    Login Successful: {state.login_successful}")
        
        return state.account_created
        
    except Exception as e:
        # Enhanced error handling with state information
        error_msg = (
            f"❌ Account creation failed: {str(e)}\n"
            f"   Registration State at Failure:\n"
            f"     Started: {state.registration_started}\n"
            f"     Form Filled: {state.form_filled}\n"
            f"     Verification Pending: {state.verification_pending}\n"
            f"     Account Created: {state.account_created}\n"
            f"     Login Successful: {state.login_successful}"
        )
        
        # Take comprehensive screenshot for debugging
        screenshot_filename = f"registration_failure_{int(asyncio.get_event_loop().time())}.png"
        try:
            await page.screenshot(path=screenshot_filename, full_page=True)
            print(f"  📸 Failure screenshot saved: {screenshot_filename}")
        except:
            pass
        
        # Log current page information
        try:
            current_url = page.url
            page_title = await page.title()
            print(f"  🌐 Current URL at failure: {current_url}")
            print(f"  📄 Page title at failure: {page_title}")
        except:
            pass
        
        raise Exception(error_msg)

async def submit_registration_form(page):
    """
    Submits the registration form using multiple selector strategies.
    
    Args:
        page: Playwright page object
        
    Returns:
        bool: True if form was successfully submitted, False otherwise
    """
    print("  🔍 Looking for submit button...")
    
    # Multiple selector strategies for submit buttons
    submit_selectors = [
        # Text-based selectors
        'button:has-text("Create Account")',
        'button:has-text("Sign Up")',
        'button:has-text("Register")',
        'button:has-text("Submit")',
        'button:has-text("Continue")',
        'input[type="submit"]',
        
        # Data attribute selectors
        'button[data-automation-id*="submit"]',
        'button[data-automation-id*="register"]',
        'button[data-automation-id*="createAccount"]',
        'button[data-automation-id*="signUp"]',
        
        # Class-based selectors
        'button[class*="submit"]',
        'button[class*="register"]',
        'button[class*="create-account"]',
        'button[class*="signup"]',
        
        # ID-based selectors
        'button[id*="submit"]',
        'button[id*="register"]',
        'button[id*="create-account"]',
        
        # Form submit selectors
        'form button[type="submit"]',
        'form input[type="submit"]'
    ]
    
    for selector in submit_selectors:
        try:
            print(f"    🔎 Trying submit selector: {selector}")
            
            element = await page.wait_for_selector(selector, timeout=3000, state='visible')
            
            if element:
                # Check if button is enabled
                is_disabled = await element.is_disabled()
                if is_disabled:
                    print(f"    ⚠️ Submit button found but disabled: {selector}")
                    continue
                
                print(f"    ✓ Found enabled submit button: {selector}")
                
                # Click the submit button
                await element.click()
                print(f"    🖱️ Clicked submit button")
                
                # Wait for form submission to process
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    print(f"    ✓ Form submission processed")
                except:
                    print(f"    ⚠️ Form submission timeout, but proceeding...")
                
                return True
                
        except Exception as e:
            continue
    
    # If no submit button found, try pressing Enter on the form
    try:
        print("    🔍 No submit button found, trying Enter key...")
        await page.keyboard.press("Enter")
        await page.wait_for_load_state("networkidle", timeout=5000)
        print("    ✓ Form submitted using Enter key")
        return True
    except:
        pass
    
    print("    ❌ Could not find or click submit button")
    return False

async def verify_account_creation_success(page):
    """
    Verifies that account creation was successful by checking for success indicators.
    
    Args:
        page: Playwright page object
        
    Returns:
        bool: True if account creation success is verified, False otherwise
    """
    print("  🔍 Verifying account creation success...")
    
    # Wait a moment for page transitions
    await asyncio.sleep(2)
    
    # Check current URL for success indicators
    current_url = page.url
    success_url_patterns = [
        '/dashboard',
        '/home',
        '/welcome',
        '/success',
        '/complete',
        '/myaccount'
    ]
    
    for pattern in success_url_patterns:
        if pattern in current_url.lower():
            print(f"    ✓ Success URL pattern detected: {pattern} in {current_url}")
            return True
    
    # Check for success messages or elements
    success_indicators = [
        'text="welcome"',
        'text="success"',
        'text="account created"',
        'text="registration complete"',
        'text="successfully registered"',
        '.success-message',
        '.welcome-message',
        '[data-automation-id*="success"]'
    ]
    
    for indicator in success_indicators:
        try:
            element = await page.wait_for_selector(indicator, timeout=3000, state='visible')
            if element:
                success_text = await element.inner_text()
                print(f"    ✓ Success indicator found: {success_text}")
                return True
        except:
            continue
    
    # Check if we can access protected content (sign of successful login)
    try:
        # Look for user-specific elements that would indicate successful login
        user_indicators = [
            '[data-automation-id*="user"]',
            '[data-automation-id*="profile"]',
            '.user-menu',
            '.profile-menu',
            'text="My Account"',
            'text="Profile"'
        ]
        
        for indicator in user_indicators:
            try:
                element = await page.wait_for_selector(indicator, timeout=2000, state='visible')
                if element:
                    print(f"    ✓ User-specific content detected: {indicator}")
                    return True
            except:
                continue
    except:
        pass
    
    print("    ⚠️ Could not verify account creation success")
    return False

async def navigate_to_registration(page):
    """
    Navigates to the account registration page by finding and clicking registration links.
    Uses multiple selector strategies to handle different page layouts and designs.
    
    Args:
        page: Playwright page object
        
    Returns:
        bool: True if successfully navigated to registration page, False otherwise
        
    Raises:
        Exception: If registration navigation fails after all attempts
    """
    print("🔍 Looking for account registration links...")
    
    # Multiple selector strategies for registration links
    registration_selectors = [
        # Text-based selectors (most common)
        'a:has-text("Create Account")',
        'a:has-text("Sign Up")',
        'a:has-text("Register")',
        'a:has-text("Create an Account")',
        'a:has-text("New Account")',
        'button:has-text("Create Account")',
        'button:has-text("Sign Up")',
        'button:has-text("Register")',
        
        # Class-based selectors
        'a[class*="create-account"]',
        'a[class*="signup"]',
        'a[class*="register"]',
        'button[class*="create-account"]',
        'button[class*="signup"]',
        'button[class*="register"]',
        
        # Data attribute selectors
        'a[data-automation-id*="createAccount"]',
        'a[data-automation-id*="signUp"]',
        'a[data-automation-id*="register"]',
        'button[data-automation-id*="createAccount"]',
        'button[data-automation-id*="signUp"]',
        'button[data-automation-id*="register"]',
        
        # ID-based selectors
        'a[id*="create-account"]',
        'a[id*="signup"]',
        'a[id*="register"]',
        'button[id*="create-account"]',
        'button[id*="signup"]',
        'button[id*="register"]',
        
        # Generic link patterns
        'a[href*="register"]',
        'a[href*="signup"]',
        'a[href*="create-account"]',
        'a[href*="createaccount"]'
    ]
    
    registration_found = False
    current_url = page.url
    
    # Try each selector strategy
    for selector in registration_selectors:
        try:
            print(f"  🔎 Trying selector: {selector}")
            
            # Wait for element to be visible with short timeout
            element = await page.wait_for_selector(selector, timeout=2000, state='visible')
            
            if element:
                print(f"  ✓ Found registration link with selector: {selector}")
                
                # Get element text for logging
                element_text = await element.inner_text()
                print(f"  📝 Link text: '{element_text.strip()}'")
                
                # Click the registration link
                await element.click()
                print("  🖱️ Clicked registration link")
                
                # Wait for page transition with multiple strategies
                try:
                    # Strategy 1: Wait for URL change
                    await page.wait_for_function(
                        f'window.location.href !== "{current_url}"',
                        timeout=10000
                    )
                    print("  ✓ Page URL changed - navigation successful")
                    registration_found = True
                    break
                    
                except:
                    # Strategy 2: Wait for registration form elements
                    try:
                        await page.wait_for_selector(
                            'input[type="email"], input[name*="email"], input[placeholder*="email" i]',
                            timeout=5000
                        )
                        print("  ✓ Registration form detected - navigation successful")
                        registration_found = True
                        break
                    except:
                        # Strategy 3: Wait for registration page indicators
                        try:
                            await page.wait_for_selector(
                                'text="Create Account", text="Sign Up", text="Register", text="Registration"',
                                timeout=5000
                            )
                            print("  ✓ Registration page content detected - navigation successful")
                            registration_found = True
                            break
                        except:
                            print("  ⚠️ Click succeeded but registration page not confirmed")
                            continue
                            
        except Exception as e:
            # Continue to next selector if current one fails
            continue
    
    if not registration_found:
        # Take screenshot for debugging
        screenshot_filename = f"registration_navigation_failed_{int(asyncio.get_event_loop().time())}.png"
        try:
            await page.screenshot(path=screenshot_filename, full_page=True)
            print(f"  📸 Screenshot saved: {screenshot_filename}")
        except Exception as screenshot_error:
            print(f"  ⚠️ Failed to capture screenshot: {screenshot_error}")
        
        # Log current page information for debugging
        current_url = page.url
        page_title = await page.title()
        print(f"  🌐 Current URL: {current_url}")
        print(f"  📄 Page title: {page_title}")
        
        # Check if we're already on a registration page
        registration_indicators = [
            'text="Create Account"',
            'text="Sign Up"',
            'text="Register"',
            'text="Registration"',
            'input[type="email"]',
            'input[placeholder*="email" i]'
        ]
        
        for indicator in registration_indicators:
            try:
                if await page.query_selector(indicator):
                    print(f"  ✓ Already on registration page (found: {indicator})")
                    return True
            except:
                continue
        
        error_msg = (
            f"❌ Registration navigation failed: Could not find registration links on page\n"
            f"   Current URL: {current_url}\n"
            f"   Page title: {page_title}\n"
            f"   Screenshot saved: {screenshot_filename}\n"
            f"   Tried {len(registration_selectors)} different selector strategies"
        )
        raise Exception(error_msg)
    
    # Final verification that we're on the registration page
    final_url = page.url
    final_title = await page.title()
    print(f"  🎯 Successfully navigated to registration page")
    print(f"  🌐 Final URL: {final_url}")
    print(f"  📄 Final title: {final_title}")
    
    # Wait for page to fully load
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
        print("  ✓ Registration page fully loaded")
    except:
        print("  ⚠️ Page load timeout, but proceeding...")
    
    return True

async def fill_registration_form(page, config):
    """
    Fills the registration form with provided configuration data.
    Uses multiple selector strategies to handle different form field layouts.
    
    Args:
        page: Playwright page object
        config: RegistrationConfig object with user data
        
    Returns:
        bool: True if form was successfully filled, False otherwise
        
    Raises:
        Exception: If form filling fails after all attempts
    """
    print("📝 Filling registration form...")
    
    # Wait for form to be fully loaded
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
        print("  ✓ Registration form loaded")
    except:
        print("  ⚠️ Form load timeout, but proceeding...")
    
    # Form field mapping with multiple selector strategies
    form_fields = {
        'first_name': {
            'value': config.first_name,
            'selectors': [
                'input[data-automation-id="firstName"]',
                'input[name="firstName"]',
                'input[name="first_name"]',
                'input[placeholder*="first name" i]',
                'input[placeholder*="given name" i]',
                'input[id*="firstName"]',
                'input[id*="first_name"]'
            ]
        },
        'last_name': {
            'value': config.last_name,
            'selectors': [
                'input[data-automation-id="lastName"]',
                'input[name="lastName"]',
                'input[name="last_name"]',
                'input[placeholder*="last name" i]',
                'input[placeholder*="surname" i]',
                'input[placeholder*="family name" i]',
                'input[id*="lastName"]',
                'input[id*="last_name"]'
            ]
        },
        'email': {
            'value': config.email,
            'selectors': [
                'input[data-automation-id="email"]',
                'input[type="email"]',
                'input[name="email"]',
                'input[placeholder*="email" i]',
                'input[id*="email"]'
            ]
        },
        'password': {
            'value': config.password,
            'selectors': [
                'input[data-automation-id="password"]',
                'input[type="password"]',
                'input[name="password"]',
                'input[placeholder*="password" i]',
                'input[id*="password"]'
            ]
        },
        'confirm_password': {
            'value': config.password,
            'selectors': [
                'input[data-automation-id="confirmPassword"]',
                'input[name="confirmPassword"]',
                'input[name="confirm_password"]',
                'input[placeholder*="confirm password" i]',
                'input[placeholder*="repeat password" i]',
                'input[id*="confirmPassword"]',
                'input[id*="confirm_password"]'
            ]
        },
        'phone': {
            'value': config.phone,
            'selectors': [
                'input[data-automation-id="phone"]',
                'input[type="tel"]',
                'input[name="phone"]',
                'input[name="phoneNumber"]',
                'input[placeholder*="phone" i]',
                'input[id*="phone"]'
            ]
        }
    }
    
    filled_fields = []
    failed_fields = []
    
    # Fill each form field
    for field_name, field_config in form_fields.items():
        field_value = field_config['value']
        
        # Skip empty optional fields
        if not field_value and field_name in ['phone']:
            print(f"  ⏭️ Skipping optional field: {field_name}")
            continue
        
        # Skip empty required fields (will be caught in validation)
        if not field_value:
            print(f"  ⚠️ Empty value for field: {field_name}")
            failed_fields.append(field_name)
            continue
        
        field_filled = False
        
        # Try each selector for this field
        for selector in field_config['selectors']:
            try:
                print(f"  🔎 Trying {field_name} with selector: {selector}")
                
                # Wait for element to be visible
                element = await page.wait_for_selector(selector, timeout=3000, state='visible')
                
                if element:
                    # Clear existing content
                    await element.click()
                    await element.fill('')
                    
                    # Fill with new value
                    await element.fill(field_value)
                    
                    # Verify the value was set
                    filled_value = await element.input_value()
                    if filled_value == field_value:
                        print(f"  ✓ Successfully filled {field_name}: {field_value}")
                        filled_fields.append(field_name)
                        field_filled = True
                        break
                    else:
                        print(f"  ⚠️ Value verification failed for {field_name}")
                        continue
                        
            except Exception as e:
                # Continue to next selector
                continue
        
        if not field_filled:
            print(f"  ❌ Failed to fill field: {field_name}")
            failed_fields.append(field_name)
    
    # Handle terms and conditions acceptance
    terms_accepted = await handle_terms_and_conditions(page)
    if terms_accepted:
        print("  ✓ Terms and conditions accepted")
    else:
        print("  ⚠️ Could not find or accept terms and conditions")
    
    # Validate form completion
    required_fields = ['first_name', 'last_name', 'email', 'password']
    missing_required = [field for field in required_fields if field in failed_fields]
    
    if missing_required:
        error_msg = (
            f"❌ Registration form filling failed: Missing required fields: {', '.join(missing_required)}\n"
            f"   Successfully filled: {', '.join(filled_fields)}\n"
            f"   Failed fields: {', '.join(failed_fields)}"
        )
        
        # Take screenshot for debugging
        screenshot_filename = f"registration_form_failed_{int(asyncio.get_event_loop().time())}.png"
        try:
            await page.screenshot(path=screenshot_filename, full_page=True)
            print(f"  📸 Screenshot saved: {screenshot_filename}")
        except:
            pass
        
        raise Exception(error_msg)
    
    print(f"  🎯 Form filling completed successfully")
    print(f"  ✅ Filled fields: {', '.join(filled_fields)}")
    
    return True

async def handle_terms_and_conditions(page):
    """
    Handles terms and conditions acceptance with multiple selector strategies.
    
    Args:
        page: Playwright page object
        
    Returns:
        bool: True if terms were found and accepted, False otherwise
    """
    print("  📋 Looking for terms and conditions...")
    
    # Multiple selector strategies for terms and conditions
    terms_selectors = [
        # Checkbox selectors
        'input[type="checkbox"][data-automation-id*="terms"]',
        'input[type="checkbox"][name*="terms"]',
        'input[type="checkbox"][id*="terms"]',
        'input[type="checkbox"] + label:has-text("terms")',
        'input[type="checkbox"] + label:has-text("agree")',
        'input[type="checkbox"] + label:has-text("accept")',
        
        # Button selectors
        'button:has-text("Accept")',
        'button:has-text("Agree")',
        'button:has-text("I Accept")',
        'button:has-text("I Agree")',
        
        # Link selectors
        'a:has-text("Accept")',
        'a:has-text("Agree")',
        
        # Generic selectors
        '[data-automation-id*="accept"]',
        '[data-automation-id*="agree"]',
        '[data-automation-id*="terms"]'
    ]
    
    for selector in terms_selectors:
        try:
            print(f"    🔎 Trying terms selector: {selector}")
            
            element = await page.wait_for_selector(selector, timeout=2000, state='visible')
            
            if element:
                # Check if it's already checked/accepted
                if await element.get_attribute('type') == 'checkbox':
                    is_checked = await element.is_checked()
                    if not is_checked:
                        await element.click()
                        print(f"    ✓ Checked terms checkbox")
                        return True
                    else:
                        print(f"    ✓ Terms checkbox already checked")
                        return True
                else:
                    # For buttons and links
                    await element.click()
                    print(f"    ✓ Clicked terms acceptance")
                    return True
                    
        except Exception as e:
            continue
    
    print("    ⚠️ No terms and conditions found")
    return False

async def handle_verification_steps(page):
    """
    Handles registration verification steps including email verification and CAPTCHA scenarios.
    
    Args:
        page: Playwright page object
        
    Returns:
        bool: True if verification completed successfully, False otherwise
        
    Raises:
        Exception: If verification fails or times out
    """
    print("🔍 Checking for verification steps...")
    
    # Check for duplicate email error first
    duplicate_email_detected = await check_duplicate_email_error(page)
    if duplicate_email_detected:
        error_msg = (
            "❌ Registration failed: Email address already exists\n"
            "   The provided email is already registered in the system.\n"
            "   Please use a different email address or try logging in instead."
        )
        
        # Take screenshot for debugging
        screenshot_filename = f"duplicate_email_error_{int(asyncio.get_event_loop().time())}.png"
        try:
            await page.screenshot(path=screenshot_filename, full_page=True)
            print(f"  📸 Screenshot saved: {screenshot_filename}")
        except:
            pass
        
        raise Exception(error_msg)
    
    # Check for CAPTCHA challenge
    captcha_detected = await check_captcha_challenge(page)
    if captcha_detected:
        print("🤖 CAPTCHA challenge detected - waiting for manual completion...")
        
        # Take screenshot for user reference
        screenshot_filename = f"captcha_challenge_{int(asyncio.get_event_loop().time())}.png"
        try:
            await page.screenshot(path=screenshot_filename, full_page=True)
            print(f"  📸 CAPTCHA screenshot saved: {screenshot_filename}")
        except:
            pass
        
        # Wait for CAPTCHA completion (user has 2 minutes)
        captcha_completed = await wait_for_captcha_completion(page)
        if not captcha_completed:
            raise Exception("❌ CAPTCHA challenge not completed within timeout period")
        
        print("  ✓ CAPTCHA challenge completed")
    
    # Check for email verification requirement
    email_verification_required = await check_email_verification_required(page)
    if email_verification_required:
        print("📧 Email verification required - waiting for manual verification...")
        
        # Take screenshot for user reference
        screenshot_filename = f"email_verification_{int(asyncio.get_event_loop().time())}.png"
        try:
            await page.screenshot(path=screenshot_filename, full_page=True)
            print(f"  📸 Email verification screenshot saved: {screenshot_filename}")
        except:
            pass
        
        print("  ⏳ Please check your email and complete verification manually")
        print("  ⏳ The automation will wait for up to 5 minutes for verification completion")
        
        # Wait for email verification completion
        verification_completed = await wait_for_email_verification(page)
        if not verification_completed:
            print("  ⚠️ Email verification not completed within timeout")
            print("  ⚠️ You may need to complete verification manually and restart the automation")
            return False
        
        print("  ✓ Email verification completed")
    
    # Check for registration success
    registration_success = await check_registration_success(page)
    if registration_success:
        print("  🎉 Registration completed successfully!")
        return True
    
    # Check for other form validation errors
    validation_errors = await check_form_validation_errors(page)
    if validation_errors:
        error_msg = (
            f"❌ Registration form validation errors detected:\n"
            f"   Errors: {', '.join(validation_errors)}\n"
            f"   Please check the form fields and try again."
        )
        
        # Take screenshot for debugging
        screenshot_filename = f"form_validation_errors_{int(asyncio.get_event_loop().time())}.png"
        try:
            await page.screenshot(path=screenshot_filename, full_page=True)
            print(f"  📸 Screenshot saved: {screenshot_filename}")
        except:
            pass
        
        raise Exception(error_msg)
    
    print("  ✓ No verification steps required")
    return True

async def check_duplicate_email_error(page):
    """Check for duplicate email error messages."""
    duplicate_error_selectors = [
        'text="already exists"',
        'text="already registered"',
        'text="email is already in use"',
        'text="account already exists"',
        '[data-automation-id*="error"]:has-text("email")',
        '.error:has-text("email")',
        '.validation-error:has-text("email")'
    ]
    
    for selector in duplicate_error_selectors:
        try:
            element = await page.wait_for_selector(selector, timeout=2000, state='visible')
            if element:
                error_text = await element.inner_text()
                if any(keyword in error_text.lower() for keyword in ['already', 'exists', 'registered', 'duplicate']):
                    print(f"  ❌ Duplicate email error detected: {error_text}")
                    return True
        except:
            continue
    
    return False

async def check_captcha_challenge(page):
    """Check for CAPTCHA challenge elements."""
    captcha_selectors = [
        'iframe[src*="captcha"]',
        'iframe[src*="recaptcha"]',
        'div[class*="captcha"]',
        'div[class*="recaptcha"]',
        '[data-automation-id*="captcha"]',
        'text="verify you are human"',
        'text="complete the challenge"'
    ]
    
    for selector in captcha_selectors:
        try:
            element = await page.wait_for_selector(selector, timeout=2000, state='visible')
            if element:
                print(f"  🤖 CAPTCHA detected with selector: {selector}")
                return True
        except:
            continue
    
    return False

async def wait_for_captcha_completion(page):
    """Wait for CAPTCHA completion with timeout."""
    timeout_seconds = 120  # 2 minutes
    check_interval = 5  # Check every 5 seconds
    
    for i in range(0, timeout_seconds, check_interval):
        try:
            # Check if CAPTCHA is still present
            captcha_still_present = await check_captcha_challenge(page)
            if not captcha_still_present:
                return True
            
            print(f"  ⏳ Waiting for CAPTCHA completion... ({timeout_seconds - i}s remaining)")
            await asyncio.sleep(check_interval)
        except:
            continue
    
    return False

async def check_email_verification_required(page):
    """Check if email verification is required."""
    verification_selectors = [
        'text="verify your email"',
        'text="check your email"',
        'text="verification email sent"',
        'text="confirm your email"',
        '[data-automation-id*="verification"]',
        '.verification-message',
        '.email-verification'
    ]
    
    for selector in verification_selectors:
        try:
            element = await page.wait_for_selector(selector, timeout=2000, state='visible')
            if element:
                verification_text = await element.inner_text()
                if any(keyword in verification_text.lower() for keyword in ['verify', 'verification', 'confirm', 'check']):
                    print(f"  📧 Email verification required: {verification_text}")
                    return True
        except:
            continue
    
    return False

async def wait_for_email_verification(page):
    """Wait for email verification completion with timeout."""
    timeout_seconds = 300  # 5 minutes
    check_interval = 10  # Check every 10 seconds
    
    for i in range(0, timeout_seconds, check_interval):
        try:
            # Check if verification is still required
            verification_still_required = await check_email_verification_required(page)
            if not verification_still_required:
                # Check if we've moved to a success page or login page
                success_detected = await check_registration_success(page)
                if success_detected:
                    return True
            
            print(f"  ⏳ Waiting for email verification... ({timeout_seconds - i}s remaining)")
            await asyncio.sleep(check_interval)
        except:
            continue
    
    return False

async def check_registration_success(page):
    """Check for registration success indicators."""
    success_selectors = [
        'text="registration successful"',
        'text="account created"',
        'text="welcome"',
        'text="registration complete"',
        'text="successfully registered"',
        '[data-automation-id*="success"]',
        '.success-message',
        '.registration-success'
    ]
    
    for selector in success_selectors:
        try:
            element = await page.wait_for_selector(selector, timeout=2000, state='visible')
            if element:
                success_text = await element.inner_text()
                if any(keyword in success_text.lower() for keyword in ['success', 'complete', 'created', 'welcome']):
                    print(f"  🎉 Registration success detected: {success_text}")
                    return True
        except:
            continue
    
    # Also check if we've been redirected to a dashboard or login page
    current_url = page.url
    if any(path in current_url.lower() for path in ['/dashboard', '/home', '/welcome', '/login']):
        print(f"  🎉 Registration success inferred from URL: {current_url}")
        return True
    
    return False

async def check_form_validation_errors(page):
    """Check for form validation errors."""
    validation_errors = []
    
    error_selectors = [
        '.error',
        '.validation-error',
        '.field-error',
        '[data-automation-id*="error"]',
        '[class*="error"]',
        'text="required"',
        'text="invalid"'
    ]
    
    for selector in error_selectors:
        try:
            elements = await page.query_selector_all(selector)
            for element in elements:
                if await element.is_visible():
                    error_text = await element.inner_text()
                    if error_text and error_text.strip():
                        validation_errors.append(error_text.strip())
        except:
            continue
    
    # Remove duplicates and return
    return list(set(validation_errors))

async def login(page):
    """
    Authenticates into Workday using credentials from environment variables.
    Uses Playwright's robust selectors to handle Workday's login form.
    """
    # Navigate to Workday tenant URL
    tenant_url = os.getenv('WORKDAY_TENANT_URL')
    print(f"🌐 Navigating to Workday tenant: {tenant_url}")
    await page.goto(tenant_url)
    
    # Fill credentials and submit - using multiple possible selectors for robustness
    email_selectors = [
        'input[data-automation-id="email"]',
        'input[type="email"]',
        'input[name="username"]'
    ]
    
    password_selectors = [
        'input[data-automation-id="password"]',
        'input[type="password"]',
        'input[name="password"]'
    ]
    
    submit_selectors = [
        'button[data-automation-id="signInSubmitButton"]',
        'button[type="submit"]',
        'button:has-text("Sign In")'
    ]
    
    # Try different selector combinations
    logged_in = False
    for email_sel in email_selectors:
        for password_sel in password_selectors:
            for submit_sel in submit_selectors:
                try:
                    await page.fill(email_sel, os.getenv('WORKDAY_USERNAME'))
                    await page.fill(password_sel, os.getenv('WORKDAY_PASSWORD'))
                    await page.click(submit_sel)
                    
                    # Wait for successful login (detect dashboard element)
                    try:
                        await page.wait_for_selector('.WDSC-Dashboard', timeout=10000)
                        logged_in = True
                        print("🔓 Login successful")
                        break
                    except:
                        continue
                except:
                    continue
            if logged_in:
                break
        if logged_in:
            break
    
    if not logged_in:
        raise Exception("❌ Login failed - check credentials or page structure")
    
    # Handle potential multi-factor authentication prompt
    try:
        mfa_prompt = await page.query_selector('text="Send Me a Push"')
        if mfa_prompt:
            print("⚠️ MFA required - please complete authentication in browser")
            # Wait for MFA completion (extend timeout)
            await page.wait_for_selector('.WDSC-Dashboard', timeout=120000)
    except:
        pass

async def authenticate_user(page, config=None):
    """
    Routes to appropriate authentication method based on CREATE_ACCOUNT_MODE.
    
    Args:
        page: Playwright page object
        config: RegistrationConfig object (optional, will create if not provided)
        
    Returns:
        bool: True if authentication was successful, False otherwise
        
    Raises:
        Exception: If authentication fails
    """
    # Create config if not provided
    if config is None:
        config = RegistrationConfig()
    
    print(f"🔐 Authentication mode: {'REGISTRATION' if config.is_registration_mode() else 'LOGIN'}")
    
    if config.is_registration_mode():
        # Validate registration configuration before proceeding
        try:
            config.validate_configuration()
            print("✅ Registration configuration validated")
            print(f"📋 {config.get_registration_summary()}")
        except (ValueError, RuntimeError) as e:
            print(f"❌ Registration configuration error: {str(e)}")
            raise
        
        # Use registration flow
        print("🚀 Starting account registration flow...")
        return await create_nvidia_account(page, config)
    else:
        # Use existing login flow
        print("🔑 Starting existing account login flow...")
        await login_existing_user(page)
        return True

async def login_existing_user(page):
    """
    Renamed version of the original login function for clarity.
    Authenticates into Workday using existing credentials from environment variables.
    """
    # Navigate to Workday tenant URL
    tenant_url = os.getenv('WORKDAY_TENANT_URL')
    print(f"🌐 Navigating to Workday tenant: {tenant_url}")
    await page.goto(tenant_url)
    
    # Fill credentials and submit - using multiple possible selectors for robustness
    email_selectors = [
        'input[data-automation-id="email"]',
        'input[type="email"]',
        'input[name="username"]'
    ]
    
    password_selectors = [
        'input[data-automation-id="password"]',
        'input[type="password"]',
        'input[name="password"]'
    ]
    
    submit_selectors = [
        'button[data-automation-id="signInSubmitButton"]',
        'button[type="submit"]',
        'button:has-text("Sign In")'
    ]
    
    # Try different selector combinations
    logged_in = False
    for email_sel in email_selectors:
        for password_sel in password_selectors:
            for submit_sel in submit_selectors:
                try:
                    await page.fill(email_sel, os.getenv('WORKDAY_USERNAME'))
                    await page.fill(password_sel, os.getenv('WORKDAY_PASSWORD'))
                    await page.click(submit_sel)
                    
                    # Wait for successful login (detect dashboard element)
                    try:
                        await page.wait_for_selector('.WDSC-Dashboard', timeout=10000)
                        logged_in = True
                        print("🔓 Login successful")
                        break
                    except:
                        continue
                except:
                    continue
            if logged_in:
                break
        if logged_in:
            break
    
    if not logged_in:
        raise Exception("❌ Login failed - check credentials or page structure")
    
    # Handle potential multi-factor authentication prompt
    try:
        mfa_prompt = await page.query_selector('text="Send Me a Push"')
        if mfa_prompt:
            print("⚠️ MFA required - please complete authentication in browser")
            # Wait for MFA completion (extend timeout)
            await page.wait_for_selector('.WDSC-Dashboard', timeout=120000)
    except:
        pass

async def crawl_application_flow(start_path, page):
    """
    Crawls through Workday application pages using BFS algorithm.
    Returns list of all discovered form elements.
    """
    visited = set()
    queue = deque([start_path])
    all_form_elements = []
    base_url = os.getenv('WORKDAY_TENANT_URL')
    
    # Counter for progress tracking
    page_count = 0
    
    while queue:
        current_path = queue.popleft()
        if current_path in visited:
            continue
            
        full_url = f"{base_url}{current_path}"
        print(f"📄 Page {page_count+1}: Navigating to {full_url}")
        
        try:
            await page.goto(full_url, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle", timeout=10000)
            
            # Extract form elements from current page
            page_elements = await extract_form_elements(page)
            all_form_elements.extend(page_elements)
            print(f"  ✓ Found {len(page_elements)} form elements")
            
            # Find new links to crawl
            new_links = await discover_application_links(page)
            for link in new_links:
                if link not in visited:
                    queue.append(link)
            
            visited.add(current_path)
            page_count += 1
            
        except Exception as e:
            print(f"  ⚠️ Error processing {current_path}: {str(e)}")
    
    return all_form_elements

async def discover_application_links(page):
    """
    Finds all relevant application links in current page.
    Filters out non-application and external links.
    """
    application_links = []
    
    # Get all links on page
    all_links = await page.query_selector_all('a[href]')
    
    for link in all_links:
        try:
            href = await link.get_attribute('href')
            if href and href.startswith('/') and not href.startswith('//'):
                # Normalize URL path
                path = href.split('?')[0]  # Remove query parameters
                
                # Filter for application-specific paths
                if any(segment in path for segment in [
                    '/myaccount/', 
                    '/application/', 
                    '/careers/',
                    '/job/',
                    '/review/',
                    '/eeo/'
                ]):
                    if path not in application_links:
                        application_links.append(path)
        except:
            continue
    
    print(f"  🔗 Found {len(application_links)} application links on this page")
    return application_links

async def extract_form_elements(page):
    """
    Extracts and classifies form elements from current page.
    Returns structured data for each form control.
    """
    form_elements = []
    
    # Find all form containers - try multiple strategies
    form_containers = await page.query_selector_all('.WDSC-FormField')
    
    # Alternative selectors if primary not found
    if not form_containers:
        form_containers = await page.query_selector_all('div[data-automation-id="formField"]')
    
    # If still no containers found, try more generic form selectors
    if not form_containers:
        # Look for individual form elements directly
        form_elements_direct = await page.query_selector_all('input, select, textarea, button[type="submit"]')
        print(f"  🔍 Found {len(form_elements_direct)} direct form elements")
        
        # Create pseudo-containers for each form element
        form_containers = form_elements_direct
    
    print(f"  🔍 Scanning {len(form_containers)} form containers")
    
    for container in form_containers:
        try:
            # Skip hidden/invisible elements
            if not await container.is_visible():
                continue
                
            # Determine control type
            control_type = await identify_control_type(container)
            
            # Skip unsupported types
            if not control_type:
                continue
                
            # Extract common properties
            element_data = {
                "label": await extract_label(container),
                "id_of_input_component": await extract_identifier(container, control_type),
                "required": await is_required(container),
                "type_of_input": control_type,
                "options": [],
                "user_data_select_values": []
            }
            
            # Handle options-based elements
            if control_type in ("select", "multiselect", "radio", "checkbox"):
                element_data["options"] = await extract_options(container, control_type)
                element_data["user_data_select_values"] = generate_sample_values(
                    control_type, 
                    element_data["options"]
                )
            
            # Special handling for date fields
            elif control_type == "date":
                element_data["options"] = ["MM", "DD", "YYYY"]
                element_data["user_data_select_values"] = ["01", "15", "2023"]
            
            # Special handling for file uploads
            elif control_type == "file":
                element_data["user_data_select_values"] = ["resume.pdf"]
            
            form_elements.append(element_data)
            
        except Exception as e:
            # Skip elements that cause errors but continue processing others
            # print(f"  ⚠️ Element extraction error: {str(e)}")
            pass
    
    return form_elements

async def identify_control_type(element):
    """
    Determines the type of form control for both containers and individual elements.
    Handles various UI patterns found in Workday applications and generic forms.
    """
    # First check if this element itself is a form control (for direct elements)
    tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
    
    if tag_name == 'input':
        input_type = await element.get_attribute('type') or 'text'
        if input_type in ['text', 'email', 'tel', 'number', 'search']:
            return "text"
        elif input_type == 'password':
            return "password"
        elif input_type == 'file':
            return "file"
        elif input_type == 'checkbox':
            return "checkbox"
        elif input_type == 'radio':
            return "radio"
        elif input_type == 'submit':
            return "submit"
        elif input_type == 'button':
            return "button"
        elif input_type == 'date':
            return "date"
        else:
            return "text"  # Default for unknown input types
    
    elif tag_name == 'textarea':
        return "textarea"
    
    elif tag_name == 'select':
        # Check if it's a multi-select
        multiple = await element.get_attribute('multiple')
        return "multiselect" if multiple else "select"
    
    elif tag_name == 'button':
        button_type = await element.get_attribute('type') or 'button'
        return "submit" if button_type == 'submit' else "button"
    
    # If it's not a direct form element, check for child elements (container approach)
    else:
        # Check for text inputs
        if await element.query_selector('input[type="text"]'):
            return "text"
        
        # Check for email inputs
        if await element.query_selector('input[type="email"]'):
            return "text"
        
        # Check for password inputs
        if await element.query_selector('input[type="password"]'):
            return "password"
        
        # Check for textareas
        if await element.query_selector('textarea'):
            return "textarea"
        
        # Check for file inputs
        if await element.query_selector('input[type="file"]'):
            return "file"
        
        # Check for dropdowns/comboboxes
        combobox = await element.query_selector('div[role="combobox"]')
        if combobox:
            # Determine if multiselect or single select
            if await combobox.get_attribute('aria-multiselectable') == "true":
                return "multiselect"
            
            # Check for type-ahead functionality
            input_inside = await combobox.query_selector('input[type="text"]')
            if input_inside:
                return "typeahead"
            return "select"
        
        # Check for select elements
        if await element.query_selector('select'):
            select_elem = await element.query_selector('select')
            multiple = await select_elem.get_attribute('multiple')
            return "multiselect" if multiple else "select"
        
        # Check for radio groups
        if await element.query_selector('div[data-automation-id="radioButtonGroup"]'):
            return "radio"
        
        # Check for individual radio buttons
        if await element.query_selector('input[type="radio"]'):
            return "radio"
        
        # Check for checkboxes
        if await element.query_selector('div[data-automation-id="checkboxGroup"]'):
            return "checkbox"
        
        # Check for individual checkboxes
        if await element.query_selector('input[type="checkbox"]'):
            return "checkbox"
        
        # Check for date pickers
        if await element.query_selector('div[data-automation-id="dateWidget"]'):
            return "date"
        
        # Check for date inputs
        if await element.query_selector('input[type="date"]'):
            return "date"
        
        # Check for submit buttons
        if await element.query_selector('button[type="submit"]'):
            return "submit"
        
        # Check for regular buttons
        if await element.query_selector('button'):
            return "button"
        
        # Check for date fields by label
        try:
            label = await extract_label(element)
            if label and any(term in label.lower() for term in ["date", "dob", "birth"]):
                return "date"
        except:
            pass
        
        # Final fallback to input type detection
        input_elem = await element.query_selector('input')
        if input_elem:
            input_type = await input_elem.get_attribute('type')
            if input_type in ["text", "email", "tel", "number"]:
                return "text"
            if input_type == "file":
                return "file"
    
    return None

async def extract_label(element):
    """
    Extracts the human-readable label for a form element.
    Handles various label patterns in Workday.
    """
    # Try multiple selector strategies
    label_selectors = [
        '[data-automation-id="label"]',
        'label',
        '.WDSC-Label',
        '.gwt-Label',
        '.css-1w6j2w'
    ]
    
    for selector in label_selectors:
        label_element = await element.query_selector(selector)
        if label_element:
            label_text = (await label_element.inner_text()).strip()
            # Clean up label text
            label_text = label_text.replace('*', '').replace(':', '').strip()
            if label_text:
                return label_text
    
    # Fallback to aria-label
    aria_label = await element.get_attribute('aria-label')
    if aria_label:
        return aria_label.strip()
    
    return "Unlabeled Field"

async def extract_identifier(element, control_type):
    """
    Gets unique identifier in priority order:
    1. data-automation-id
    2. id attribute
    3. name attribute
    4. Generates a unique ID based on label and type
    """
    # Try to get automation ID first
    automation_id = await element.get_attribute('data-automation-id')
    if automation_id:
        return automation_id
    
    # Try different selectors based on control type
    if control_type in ("text", "textarea", "file", "typeahead"):
        input_element = await element.query_selector('input, textarea')
        if input_element:
            element_id = await input_element.get_attribute('id')
            if element_id:
                return element_id
            
            name_attr = await input_element.get_attribute('name')
            if name_attr:
                return name_attr
    
    # For radio groups and checkboxes
    if control_type in ("radio", "checkbox"):
        first_option = await element.query_selector('input[type="radio"], input[type="checkbox"]')
        if first_option:
            return await first_option.get_attribute('name') or ""
    
    # Fallback: Generate ID from label
    label = await extract_label(element)
    if label:
        # Create slug from label
        slug = ''.join(c if c.isalnum() else '_' for c in label)
        return f"generated_{slug[:30]}"
    
    return "no_identifier_found"

async def is_required(element):
    """
    Checks if a form element is marked as required.
    Uses multiple indicators to determine requirement status.
    """
    # Check for explicit ARIA attribute
    if await element.query_selector('[aria-required="true"]'):
        return True
    
    # Check for required class
    if await element.query_selector('.WDSC-Required'):
        return True
    
    # Check for asterisk in label
    label_element = await element.query_selector('[data-automation-id="label"]')
    if label_element:
        label_text = await label_element.inner_text()
        if '*' in label_text:
            return True
    
    # Check for required text
    required_text = await element.query_selector('text="required"')
    if required_text:
        return True
    
    return False

async def extract_options(element, control_type):
    """
    Extracts available options for multi-choice controls.
    Handles lazy-loaded dropdowns and dynamic content.
    """
    options = []
    
    if control_type in ("select", "multiselect", "typeahead"):
        # Handle dropdown options
        try:
            # Click to open dropdown
            await element.click()
            await asyncio.sleep(0.5)  # Allow options to render
            
            # Get all visible options
            option_elements = await element.query_selector_all('div[role="option"]')
            
            for opt in option_elements:
                # Skip invisible options
                if not await opt.is_visible():
                    continue
                    
                option_text = (await opt.inner_text()).strip()
                if option_text:
                    options.append(option_text)
            
            # Close dropdown
            await element.press("Escape")
        except Exception as e:
            print(f"    ⚠️ Couldn't extract options: {str(e)}")
        
    elif control_type == "radio":
        # Extract radio options
        option_elements = await element.query_selector_all('[data-automation-id="radioLabel"]')
        options = [await opt.inner_text() for opt in option_elements]
        
    elif control_type == "checkbox":
        # Extract checkbox options
        option_elements = await element.query_selector_all('[data-automation-id="checkboxLabel"]')
        options = [await opt.inner_text() for opt in option_elements]
    
    # Filter empty options and return unique values
    return list(set(opt for opt in options if opt))

def generate_sample_values(control_type, options):
    """
    Generates sample values based on control type and available options.
    Uses intelligent selection for realistic data.
    """
    if not options:
        return []
    
    # Handle different control types
    if control_type in ("select", "radio", "typeahead"):
        # Prefer "No" for visa questions, "Yes" for authorization
        for opt in options:
            opt_lower = opt.lower()
            if "no" in opt_lower or "not" in opt_lower or "don't" in opt_lower:
                return [opt]
        return [options[0]]  # First option as fallback
    
    if control_type in ("multiselect", "checkbox"):
        # Select a single option for multiselects
        return [options[0]] if options else []
    
    return []

async def main():
    """
    Main execution flow:
    1. Initialize and validate configuration
    2. Setup browser with authentication state
    3. Authenticate (login or register) to Workday
    4. Crawl application pages
    5. Extract form data
    6. Save results
    """
    print("🚀 Starting Workday Form Scraper")
    print("--------------------------------")
    
    # Initialize and validate configuration at startup
    config = None
    try:
        config = RegistrationConfig()
        
        # Validate configuration if in registration mode
        if config.is_registration_mode():
            print("🔧 Registration mode enabled - validating configuration...")
            config.validate_configuration()
            print("✅ Registration configuration validated successfully")
            print(f"📋 {config.get_registration_summary()}")
        else:
            print("🔧 Login mode enabled - using existing credentials")
            
    except (ValueError, RuntimeError) as config_error:
        print(f"❌ Configuration error: {str(config_error)}")
        print("💡 Please check your .env file and ensure all required variables are set")
        return
    except Exception as unexpected_error:
        print(f"❌ Unexpected configuration error: {str(unexpected_error)}")
        return
    
    browser = None
    try:
        async with async_playwright() as p:
            # Launch browser (headless=False for debugging)
            browser = await p.chromium.launch(headless=False)
            context = None
            
            # Check if we have saved authentication state
            if os.path.exists(AUTH_STATE_FILE):
                print("🔑 Loading authentication state from file")
                try:
                    context = await browser.new_context(storage_state=AUTH_STATE_FILE)
                    print("   ✓ Authentication state loaded")
                except Exception as e:
                    print(f"   ⚠️ Error loading auth state: {str(e)}")
                    print("   ⚠️ Proceeding with new session")
                    context = await browser.new_context()
            else:
                context = await browser.new_context()
            
            page = await context.new_page()
            page.set_default_timeout(60000)  # 60-second timeout
            
            try:
                # Navigate to the target page (job application or account home)
                start_url = get_target_url()
                print(f"🌐 Navigating to: {start_url}")
                await page.goto(start_url)
                
                # Detect if we need to authenticate
                if await page.query_selector('input[data-automation-id="email"]'):
                    print("🔐 Authentication required")
                    auth_success = await authenticate_user(page, config)
                    if not auth_success:
                        raise Exception("❌ Authentication failed")
                    
                    # Save authentication state for future runs
                    await context.storage_state(path=AUTH_STATE_FILE)
                    print(f"💾 Saved authentication state to {AUTH_STATE_FILE}")
                else:
                    print("✅ Already authenticated or on public page")
                
                # Start crawling from current page
                print("\n🔍 Starting application crawl")
                current_path = page.url.replace(os.getenv('WORKDAY_TENANT_URL'), '')
                form_data = await crawl_application_flow(current_path, page)
                
                # Save results
                with open(OUTPUT_FILE, 'w') as f:
                    json.dump(form_data, f, indent=2)
                    
                print(f"\n✅ Success! Extracted {len(form_data)} form elements")
                print(f"📁 Output saved to {OUTPUT_FILE}")
                
                # Print summary of findings
                control_counts = {}
                for item in form_data:
                    ctype = item["type_of_input"]
                    control_counts[ctype] = control_counts.get(ctype, 0) + 1
                
                print("\n📊 Extracted Control Types:")
                for ctype, count in control_counts.items():
                    print(f"  {ctype.capitalize().ljust(12)}: {count}")
                
            except Exception as e:
                # Enhanced error handling with registration-specific guidance
                error_message = str(e)
                
                # Take comprehensive screenshot for debugging
                screenshot_filename = f"main_execution_error_{int(asyncio.get_event_loop().time())}.png"
                try:
                    await page.screenshot(path=screenshot_filename, full_page=True)
                    print(f"📸 Error screenshot saved: {screenshot_filename}")
                except:
                    pass
                
                # Log current page information
                try:
                    current_url = page.url
                    page_title = await page.title()
                    print(f"🌐 Current URL at error: {current_url}")
                    print(f"📄 Page title at error: {page_title}")
                except:
                    pass
                
                # Provide specific guidance based on error type
                if "Registration" in error_message or "registration" in error_message:
                    print(f"\n❌ Registration error: {error_message}")
                    print("💡 Registration troubleshooting tips:")
                    print("   - Ensure CREATE_ACCOUNT_MODE=true in your .env file")
                    print("   - Verify all registration fields are filled in .env")
                    print("   - Check if the email address is already registered")
                    print("   - Try using a different email address")
                elif "Authentication failed" in error_message:
                    print(f"\n❌ Authentication error: {error_message}")
                    print("💡 Authentication troubleshooting tips:")
                    if config and config.is_registration_mode():
                        print("   - Registration mode: Check registration credentials in .env")
                        print("   - Ensure the email address is not already registered")
                    else:
                        print("   - Login mode: Check WORKDAY_USERNAME and WORKDAY_PASSWORD in .env")
                        print("   - Verify credentials are correct for the Workday tenant")
                elif "Login failed" in error_message:
                    print(f"\n❌ Login error: {error_message}")
                    print("💡 Login troubleshooting tips:")
                    print("   - Verify WORKDAY_USERNAME and WORKDAY_PASSWORD in .env file")
                    print("   - Check if the Workday tenant URL is correct")
                    print("   - Ensure your account is not locked or suspended")
                else:
                    print(f"\n❌ Critical error: {error_message}")
                    print("💡 General troubleshooting tips:")
                    print("   - Check your internet connection")
                    print("   - Verify the Workday tenant URL is accessible")
                    print("   - Review the error screenshot for visual clues")
                
                # Save partial results if possible
                if 'form_data' in locals() and form_data:
                    partial_filename = f'partial_{OUTPUT_FILE}'
                    with open(partial_filename, 'w') as f:
                        json.dump(form_data, f, indent=2)
                    print(f"💾 Saved partial results to {partial_filename}")
                
                # Re-raise the exception to maintain error status
                raise
                
            finally:
                # Ensure proper cleanup of browser context
                if context:
                    await context.close()
                    
    except Exception as e:
        # Final error handling for any uncaught exceptions
        print(f"\n💥 Fatal error: {str(e)}")
        return
    finally:
        # Ensure browser is always closed
        if browser:
            await browser.close()
            print("\n🛑 Browser closed")

if __name__ == "__main__":
    asyncio.run(main())