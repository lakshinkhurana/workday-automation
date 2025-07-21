#!/usr/bin/env python3
"""
Workday Application Automation Suite - Fixed Version
Author: Web Automation Engineer
Date: 2023-11-25
"""
import os
import json
import asyncio
import sys
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Load environment variables with error handling
try:
    load_dotenv()
    REQUIRED_ENV = [
        'WORKDAY_TENANT_URL',
        'WORKDAY_USERNAME',
        'WORKDAY_PASSWORD',
        'JOB_URL'
    ]
    
    missing = [var for var in REQUIRED_ENV if not os.getenv(var)]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("ℹ️ Create a .env file with these variables:")
        print("\n".join(REQUIRED_ENV))
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Environment loading error: {str(e)}")
    sys.exit(1)

# Configuration constants
AUTH_STATE_FILE = "workday_auth_state.json"
OUTPUT_FILE = "workday_forms.json"
RESUME_PATH = os.getenv('RESUME_PATH', 'resume.pdf')

async def login(page):
    """Fixed login function with NVIDIA-specific selectors"""
    tenant_url = os.getenv('WORKDAY_TENANT_URL')
    print(f"🌐 Navigating to: {tenant_url}")
    await page.goto(tenant_url, wait_until="domcontentloaded")
    await page.wait_for_load_state("networkidle", timeout=10000)
    
    # NVIDIA-specific login flow
    try:
        print("🔍 Looking for Sign In link...")
        # Try multiple selectors for Sign In
        sign_in_selectors = [
            'text="Sign In"',
            'a:has-text("Sign In")',
            'button:has-text("Sign In")',
            'button[type="submit"]',
            '[data-automation-id="signInLink"]',
            '.css-sign-in'
        ]
        
        sign_in_found = False
        for selector in sign_in_selectors:
            try:
                sign_in_link = await page.wait_for_selector(selector, timeout=3000)
                if sign_in_link and await sign_in_link.is_visible():
                    print(f"✓ Found Sign In with selector: {selector}")
                    await sign_in_link.click()
                    await page.wait_for_load_state("networkidle", timeout=10000)
                    sign_in_found = True
                    break
            except:
                continue
        
        if not sign_in_found:
            print("⚠️ Sign In link not found, assuming already on login page")
            
    except Exception as e:
        print(f"⚠️ Sign In link handling failed: {str(e)}")
    
    # Wait a bit for page to stabilize
    await asyncio.sleep(2)
    
    # Fill credentials with better error handling
    username = os.getenv('WORKDAY_USERNAME')
    password = os.getenv('WORKDAY_PASSWORD')
    
    print(f"🔑 Attempting to fill credentials for: {username}")
    
    try:
        # Try multiple selectors for email/username field
        email_selectors = [
            'input[type="email"]',
            'input[name="username"]',
            'input[name="email"]',
            'input[data-automation-id="email"]',
            '#username',
            '#email'
        ]
        
        email_filled = False
        for selector in email_selectors:
            try:
                email_field = await page.wait_for_selector(selector, timeout=3000)
                if email_field and await email_field.is_visible():
                    await email_field.fill(username)
                    print(f"✓ Filled email with selector: {selector}")
                    email_filled = True
                    break
            except:
                continue
        
        if not email_filled:
            raise Exception("Could not find email/username field")
            
        # Try multiple selectors for password field
        password_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[data-automation-id="password"]',
            '#password'
        ]
        
        password_filled = False
        for selector in password_selectors:
            try:
                password_field = await page.wait_for_selector(selector, timeout=3000)
                if password_field and await password_field.is_visible():
                    await password_field.fill(password)
                    print(f"✓ Filled password with selector: {selector}")
                    password_filled = True
                    break
            except:
                continue
        
        if not password_filled:
            raise Exception("Could not find password field")
            
    except Exception as e:
        print(f"❌ Failed to fill credentials: {str(e)}")
        await page.screenshot(path='login_error.png')
        raise
    
    # Click submit button with multiple selectors
    try:
        print("🔄 Attempting to submit login...")
        submit_selectors = [
            'button:has-text("Sign In")',
            'button:has-text("Log In")',
            'button:has-text("Login")',
            'button[type="submit"]',
            'input[type="submit"]',
            '[data-automation-id="signInSubmitButton"]'
        ]
        
        submit_clicked = False
        for selector in submit_selectors:
            try:
                submit_btn = await page.wait_for_selector(selector, timeout=3000)
                if submit_btn and await submit_btn.is_visible():
                    await submit_btn.click()
                    print(f"✓ Clicked submit with selector: {selector}")
                    submit_clicked = True
                    break
            except:
                continue
        
        if not submit_clicked:
            # Try pressing Enter as fallback
            await page.keyboard.press('Enter')
            print("✓ Pressed Enter as fallback")
            
    except Exception as e:
        print(f"❌ Failed to submit login: {str(e)}")
        await page.screenshot(path='submit_error.png')
        raise
    
    # Wait for login completion with better detection
    print("⏳ Waiting for login completion...")
    
    # Wait for page to load after login attempt
    await asyncio.sleep(3)
    
    try:
        # Check if we're still on login page (indicates failure)
        login_indicators = [
            'input[type="email"]',
            'input[type="password"]',
            'button:has-text("Sign In")',
            'text="Sign In"'
        ]
        
        still_on_login = False
        for indicator in login_indicators:
            try:
                element = await page.query_selector(indicator)
                if element and await element.is_visible():
                    still_on_login = True
                    break
            except:
                continue
        
        if still_on_login:
            print("❌ Still on login page - login likely failed")
            await page.screenshot(path='login_failed.png')
            print("📷 Saved login failure screenshot: login_failed.png")
        else:
            print("✓ No longer on login page - login likely successful")
        
        # Try to find success indicators
        success_selectors = [
            '.WDSC-Dashboard',
            '[data-automation-id="dashboard"]',
            'text="Dashboard"',
            'text="My Account"',
            '.workday-dashboard',
            '[data-automation-id="globalNavigationMenu"]',
            '.css-1w6j2w',
            'text="Jobs"',
            'text="Career"'
        ]
        
        login_success = False
        for selector in success_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=2000)
                if element and await element.is_visible():
                    print(f"🔓 Login successful - found: {selector}")
                    login_success = True
                    break
            except:
                continue
        
        if not login_success and not still_on_login:
            # Take screenshot of current page for debugging
            await page.screenshot(path='post_login_page.png')
            print("📷 Saved post-login page screenshot: post_login_page.png")
            print("⚠️ Login verification inconclusive - continuing anyway")
            
            # Print current URL for debugging
            current_url = page.url
            print(f"🔗 Current URL: {current_url}")
            
            # Print page title for debugging
            try:
                title = await page.title()
                print(f"📄 Page title: {title}")
            except:
                pass
            
    except Exception as e:
        print(f"⚠️ Login verification error: {str(e)} - continuing anyway")
        await page.screenshot(path='login_verification_error.png')
        print("📷 Saved verification error screenshot: login_verification_error.png")

async def navigate_to_job_application(page):
    """Fixed job navigation for NVIDIA"""
    job_url = os.getenv('JOB_URL')
    print(f"🔍 Navigating to job: {job_url}")
    await page.goto(job_url)
    
    # Handle "Apply" button variations
    apply_selectors = [
        'button:has-text("Apply")',
        'button:has-text("Apply Now")',
        'button[data-automation-id="applyButton"]'
    ]
    
    for selector in apply_selectors:
        try:
            apply_btn = await page.query_selector(selector)
            if apply_btn and await apply_btn.is_visible():
                await apply_btn.click()
                await page.wait_for_selector('.css-1w6j2w', timeout=10000)
                print("✓ Application started")
                return True
        except:
            continue
    
    print("⚠️ Apply button not found - continuing with current page")
    return True

async def upload_resume(page):
    """Fixed resume upload for NVIDIA"""
    resume_path = RESUME_PATH
    if not os.path.exists(resume_path):
        print(f"⚠️ Resume not found at {resume_path}")
        return False

    try:
        # Wait for file input to appear
        await page.wait_for_selector('input[type="file"]', timeout=5000)
        await page.set_input_files('input[type="file"]', resume_path)
        
        # Wait for upload confirmation
        await page.wait_for_selector('.css-1w6j2w', timeout=10000)
        print("✓ Resume uploaded")
        return True
    except Exception as e:
        print(f"⚠️ Resume upload failed: {str(e)}")
        return False

async def main():
    print("🚀 Starting NVIDIA Workday Automation")
    print("------------------------------------")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(60000)
        
        try:
            # Step 1: Login
            await login(page)
            
            # Step 2: Start application
            await navigate_to_job_application(page)
            
            # Step 3: Upload resume
            await upload_resume(page)
            
            # Step 4: Wait for form to appear
            await page.wait_for_selector('.css-1w6j2w', timeout=10000)
            print("✓ Application form loaded")
            
            # Step 5: Save successful state
            await context.storage_state(path=AUTH_STATE_FILE)
            print(f"💾 Saved authentication state")
            
            # (Optional) Add form extraction/filling here
            print("✅ Automation completed successfully")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            # Take screenshot for debugging
            await page.screenshot(path='error_screenshot.png')
            print("📷 Saved error screenshot: error_screenshot.png")
        finally:
            await browser.close()
            print("🛑 Browser closed")

if __name__ == "__main__":
    asyncio.run(main())