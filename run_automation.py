

import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Import the new modular components
from extraction import WorkdayScraper
from mapping import DataMapper
from filling import FormFiller
from base_exceptions import AutomationCompleteException

async def main():
    """
    Main function to orchestrate the Workday automation process.
    """
    load_dotenv()

    tenant_url = os.getenv('WORKDAY_TENANT_URL')
    if not tenant_url:
        print("Error: WORKDAY_TENANT_URL is not set in the .env file.")
        return

    async with async_playwright() as p:
        # Configure the browser
        browser = await p.chromium.launch(headless=False) # Set to True for headless mode
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # The entire process (extraction, mapping, and filling) is now handled by the scraper.
            print("🚀 --- Starting Workday Automation ---")
            scraper = WorkdayScraper(tenant_url)
            await scraper.scrape_site(page)
            
            if os.getenv("WORKDAY_END_URL") and page.url == os.getenv("WORKDAY_END_URL"):
              print("  ✅ Application complete.")
              raise AutomationCompleteException("Reached the Review step, ending traversal.")

            print("\n🎉 Automation process finished. The browser will close in 10 seconds. 🎉")
            await asyncio.sleep(10)

        except AutomationCompleteException as e:
            e.display_completion_message()
        except Exception as e:
            print(f"An error occurred during the automation process: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

