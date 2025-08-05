
"""
filling.py

This module automates the filling of web forms based on mapped data.
It takes a list of MappedField objects and uses Playwright to interact
with the web page and fill in the form fields.
"""

import asyncio
import os
from typing import List
from playwright.async_api import Page, Locator

# Assuming mapping.py is in the same directory and defines MappedField
# In a real project, you might have a shared types module.
from mapping import MappedField

class FormFiller:
    """    Handles the automated filling of form fields on a web page.
    This is a refactored and lightweight version of the original DirectFormFiller.
    """

    async def create_account(self, page: Page) -> bool:
        """
        Creates a new account using the specified data-automation-ids.

        Args:
            page: The Playwright Page object.

        Returns:
            True if account creation was successful, False otherwise.
        """
        print("🔐 Attempting to create a new account...")
        try:
            # Retrieve credentials from environment variables
            email = os.getenv("WORKDAY_USERNAME")
            password = os.getenv("WORKDAY_PASSWORD")

            if not email or not password:
                print("  ❌ Error: WORKDAY_USERNAME or WORKDAY_PASSWORD not set in .env file.")
                return False

            # Fill the form fields using data-automation-id
            await page.locator('[data-automation-id="email"]').fill(email)
            await page.locator('[data-automation-id="password"]').fill(password)
            await page.locator('[data-automation-id="verifyPassword"]').fill(password)
            
            print("  ✅ Filled email and password fields.")

            # Click the checkbox-like element
            await page.locator('[data-automation-id="createAccountCheckbox"]').click()
            print("  ✅ Clicked the account creation checkbox.")

            # Click the submit button, ensuring it's a button element
            await page.locator('button[data-automation-id="createAccountSubmitButton"]').click(force=True)
            print("  ✅ Clicked the create account submit button.")

            # Wait for navigation to complete, indicating success
            await page.wait_for_load_state("networkidle", timeout=30000)
            
            print("🎉 Account creation successful.")
            return True
        except Exception as e:
            print(f"  ❌ Error during account creation: {e}")
            return False
      

    async def fill_all_forms(self, page: Page, mapped_fields: List[MappedField]):
        """
        Fills all mapped form fields, navigating between pages as needed.

        Args:""
            page: The Playwright Page object to interact with.
            mapped_fields: A list of MappedField objects from the data mapping phase.
        """
        # Group fields by page to handle multi-page applications efficiently

        fields_by_page = {}
        for field in mapped_fields:
            if field.page_url not in fields_by_page:
                fields_by_page[field.page_url] = []
            fields_by_page[field.page_url].append(field)

        for page_url, fields in fields_by_page.items():
            if page.url != page_url:
                print(f"➡️ Navigating to {page_url} to fill {len(fields)} fields.")
                await page.goto(page_url, wait_until="networkidle")
            
            print(f"✍️ Filling {len(fields)} fields on page: {page.url}")
            for field in fields:
                await self._fill_field(page, field)
            
            # After filling all fields on a page, try to proceed
            await self._navigate_to_next_page(page)

        print("✅ Form filling process complete.")

    async def fill_fields_on_current_page(self, page: Page, mapped_fields: List[MappedField]):
        """
        Fills only the fields provided for the current page, without navigating.
        """
        print(f"✍️ Filling {len(mapped_fields)} fields on the current page.")
        for field in mapped_fields:
            await self._fill_field(page, field)

    async def _fill_field(self, page: Page, field: MappedField) -> bool:
      """
        Fills a single form field based on its type and mapped value.
      """
      try:
        # Use a robust selector strategy to find the element
        element_selector = f'[data-automation-id="{field.field_id}"], [id="{field.field_id}"], [name="{field.field_id}"]'
        element = page.locator(element_selector).first

        await asyncio.sleep(0.5)  # Allow time for the element to be ready

        if not await element.is_visible():
            print(f"  ⚠️ Warning: Field '{field.label}' ({field.field_id}) is not visible. Skipping.")
            return False

        # Define fill methods
        fill_method_map = {
            'text': self._fill_text_field,
            'email': self._fill_text_field,
            'tel': self._fill_text_field,
            'password': self._fill_text_field,
            'textarea': self._fill_text_field,
            'select': self._fill_select_field,
            'dropdown': self._fill_dropdown_field,
            'checkbox': self._fill_checkbox_field,
            'radio': self._fill_radio_field,  # This now correctly passes the element
            'file-selector': lambda _, file_path: self._upload_cv_file(
                page.locator('input[data-automation-id="file-upload-input-ref"]'), file_path
            ),
        }

        fill_method = fill_method_map.get(field.field_type)
        if fill_method:
          if field.field_id=='source--source' or field.field_id=='source--sourceId':
            # Special handling for the source field
            await element.type(field.value_to_fill, delay=100)
            await element.press('Enter')
          else:
            try:
                if await element.input_value() == str(field.value_to_fill):
                    print(f"  🛑 Info: Field '{field.label}' already has the correct value. Skipping.")
                    return True
            except Exception:
                # If input_value() is not applicable (e.g., for custom dropdowns) or fails,
                # we proceed with the specific fill method.
                pass
            
            await fill_method(element, field.value_to_fill)
            print(f"  ✅ Successfully filled '{field.label}'.")
            await asyncio.sleep(0.3)
            return True
        else:
            print(f"  🤔 Warning: Unsupported field type '{field.field_type}' for field '{field.label}'.")
            return False

      except Exception as e:
        print(f"  ❌ Error filling field '{field.label}' ({field.field_id}): {e}")
        return False

    async def _fill_text_field(self, element: Locator, value: str):
        """Fills a text-based input or textarea field."""
        await element.fill(value)

    async def _fill_select_field(self, element: Locator, value: str):
        """Selects an option in a standard <select> element."""
        try:
            await element.select_option(label=value)
        except Exception:
            # Fallback for when label doesn't match, try matching by value attribute
            await element.select_option(value=value)

    async def _fill_dropdown_field(self, element: Locator, value: str):
        """Handles custom dropdowns that are typically a button opening a listbox."""
        await element.click()
        await asyncio.sleep(0.5) # Wait for dropdown options to appear
        option_selector = f'[role="option"]:has-text("{value}")'
        await element.page.click(option_selector)

    async def _fill_checkbox_field(self, element: Locator, should_be_checked: bool):
        """Checks or unchecks a checkbox field based on the boolean value."""
        if should_be_checked and not await element.is_checked():
            await element.check()
        elif not should_be_checked and await element.is_checked():
            await element.uncheck()

    async def _fill_radio_field(self, element: Locator, value: str):
        """Fills a radio button group by selecting the option that matches the given value.

        This function identifies the radio button group by the 'name' attribute of the
        provided element, then selects the radio button within that group whose 'value'
        attribute corresponds to the provided value (e.g., 'Yes'/'No' mapped to 'true'/'false').
        """
        try:
            name = await element.get_attribute('name')
            if not name:
                print(f"  ⚠️ Warning: Radio input for value '{value}' lacks a 'name' attribute. Cannot select group.")
                return

            # Map common affirmative/negative values to boolean strings used in HTML
            target_value = value.lower()
            if target_value == 'yes':
                target_value = 'true'
            elif target_value == 'no':
                target_value = 'false'

            # Construct a selector for the specific radio button to check
            radio_to_select_selector = f'input[type="radio"][name="{name}"][value="{target_value}"]'
            radio_to_select = element.page.locator(radio_to_select_selector)

            if await radio_to_select.count() > 0 and await radio_to_select.is_visible():
                await radio_to_select.check()
            else:
                # Fallback for cases where the value might be different, e.g. 'Yes' instead of 'true'
                radio_to_select_selector_alt = f'input[type="radio"][name="{name}"][value="{value.lower()}"]'
                radio_to_select_alt = element.page.locator(radio_to_select_selector_alt)
                if await radio_to_select_alt.count() > 0 and await radio_to_select_alt.is_visible():
                    await radio_to_select_alt.check()
                else:
                    print(f"  ❌ Error: Could not find a visible radio button for name '{name}' with value '{value}' or '{target_value}'.")

        except Exception as e:
            # It's helpful to know which field failed.
            name_for_error = await element.get_attribute('name') or "unknown"
            print(f"  ❌ Error filling radio field '{name_for_error}' with value '{value}': {e}")
            
    async def _upload_cv_file(self, element: Locator, file_path: str):
        """
        Uploads a CV file to a file input field.
        Assumes the file path is valid and points to a CV document.
        """
        if not os.path.exists(file_path):
            print(f"  ❌ Error: File '{file_path}' does not exist.")
            return
        
        try:
            await element.set_input_files(file_path)
            print(f"  ✅ Successfully uploaded CV file: {file_path}")
            await asyncio.sleep(3)  # Allow time for the upload to process
        except Exception as e:
            print(f"  ❌ Error uploading file '{file_path}': {e}")

    async def _navigate_to_next_page(self, page: Page) -> bool:
        """
        Finds and clicks a 'Continue', 'Next', or 'Save and Continue' button.
        """
        print("  ➡️ Attempting to navigate to the next page...")
        # A list of common selectors for navigation buttons, ordered by preference
        nav_selectors = [
            'button[data-automation-id="pageFooterNextButton"]',
            'button:has-text("Save and Continue")',
            'button:has-text("Continue")',
            'button:has-text("Next")',
            'button[type="submit"]',
        ]

        for selector in nav_selectors:
            try:
                button = page.locator(selector).first
                if await button.is_visible(timeout=3000):
                    button_text = await button.inner_text()
                    print(f"    ✅ Found and clicked '{button_text}'.")
                    await button.click()
                    await page.wait_for_load_state("networkidle", timeout=30000)
                    return True
            except Exception:
                continue # Try the next selector in the list

        print("  🛑 Info: Could not find a button to navigate to the next page. Process may be complete.")
        return False
