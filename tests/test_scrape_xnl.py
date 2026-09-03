from playwright.sync_api import sync_playwright

from pond.scrape_xnl import acknowledge_notices


def test_acknowledge_notices_checks_and_dismisses_arbitrary_notices() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(
            """
            <script>
              function closeNotice(button) {
                const notice = button.parentElement;
                notice.style.display = 'none';
                if (notice.nextElementSibling) {
                  notice.nextElementSibling.style.display = 'block';
                }
              }
            </script>
            <div class="xn-alerts">
              <xn-notice-component>
                <div class="xn-heading">An entirely new notice</div>
                <div class="xn-do-not-show"
                     onclick="this.querySelector('input').checked = true">
                  <input type="checkbox">
                </div>
                 <div class="xn-close" style="width: 20px; height: 20px"
                     onclick="closeNotice(this)"></div>
              </xn-notice-component>
              <xn-notice-component style="display: none">
                <div class="xn-heading">A later unrelated notice</div>
                <div class="xn-do-not-show"
                     onclick="this.querySelector('input').checked = true">
                  <input type="checkbox">
                </div>
                <div class="xn-close" style="width: 20px; height: 20px"
                     onclick="closeNotice(this)"></div>
              </xn-notice-component>
            </div>
            """
        )

        headings = acknowledge_notices(page)

        assert headings == ["An entirely new notice", "A later unrelated notice"]
        checkboxes = page.locator('input[type="checkbox"]')
        assert all(checkboxes.nth(index).is_checked() for index in range(checkboxes.count()))
        assert page.locator("xn-notice-component:visible").count() == 0
        browser.close()


def test_acknowledge_notices_does_nothing_when_no_notice_is_visible() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content('<div class="xn-alerts"></div>')

        assert acknowledge_notices(page) == []
        browser.close()