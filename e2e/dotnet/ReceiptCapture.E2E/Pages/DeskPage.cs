using System.Text.Json;
using OpenQA.Selenium;
using OpenQA.Selenium.Support.UI;
using ReceiptCapture.E2E.Support;

namespace ReceiptCapture.E2E.Pages;

/// <summary>Shared helpers for any page inside the Frappe desk (/app/...).</summary>
public class DeskPage(IWebDriver driver)
{
    protected static readonly TimeSpan DefaultTimeout = TimeSpan.FromSeconds(20);

    protected IWebDriver Driver { get; } = driver;
    private IJavaScriptExecutor Js => (IJavaScriptExecutor)Driver;

    public void GoTo(string route)
    {
        Driver.Navigate().GoToUrl($"{TestSettings.BaseUrl}/app/{route}");
        WaitUntilIdle();
    }

    protected T WaitFor<T>(Func<IWebDriver, T> condition, string message, TimeSpan? timeout = null)
    {
        var wait = new WebDriverWait(Driver, timeout ?? DefaultTimeout) { Message = message };
        // Frappe re-renders often; an element found a moment ago may have been replaced
        wait.IgnoreExceptionTypes(typeof(StaleElementReferenceException));
        return wait.Until(condition);
    }

    /// <summary>Frappe renders asynchronously: wait until the page is loaded, no request is running and nothing is frozen.</summary>
    public void WaitUntilIdle(TimeSpan? timeout = null) =>
        WaitFor(_ => (bool)Js.ExecuteScript("""
            return document.readyState === "complete"
                && !!window.frappe && !!frappe.boot
                && !(frappe.request && frappe.request.ajax_count)
                && !document.querySelector("#freeze.in");
            """)!, "Desk did not become idle", timeout);

    /// <summary>
    /// First visible match. Frappe keeps previously visited pages in the DOM (hidden), so the
    /// first match in document order can belong to a page that is no longer on screen.
    /// </summary>
    public IWebElement? Visible(string css)
    {
        foreach (var element in Driver.FindElements(By.CssSelector(css)))
        {
            try
            {
                if (element.Displayed) return element;
            }
            catch (StaleElementReferenceException)
            {
                // Re-rendered while we looked at it; the next poll finds the new element
            }
        }
        return null;
    }

    public IWebElement FindVisible(string css, TimeSpan? timeout = null) =>
        WaitFor(_ => Visible(css), $"{css} is not visible", timeout)!;

    public IWebElement Find(string css) =>
        WaitFor(d => d.FindElements(By.CssSelector(css)).FirstOrDefault(), $"No element matches {css}")!;

    public bool IsPresent(string css) => Visible(css) is not null;

    /// <summary>Clicks the visible element, retrying if Frappe re-renders it between finding and clicking.</summary>
    public void Click(string css) =>
        WaitFor(_ =>
        {
            var element = Visible(css);
            if (element is null || !element.Enabled) return false;
            try
            {
                element.Click();
                return true;
            }
            catch (ElementClickInterceptedException)
            {
                return false;
            }
        }, $"Could not click {css}");

    public void TypeInto(string css, object value)
    {
        WaitFor(_ =>
        {
            var input = Visible(css);
            if (input is null) return false;
            input.SendKeys(Keys.Control + "a");
            input.SendKeys(value + Keys.Tab);
            return true;
        }, $"Could not type into {css}");
        WaitUntilIdle();
    }

    /// <summary>Status pill in the page header, e.g. "Draft" or "Extracted".</summary>
    public string Status => FindVisible(".page-head .indicator-pill").Text;

    // ---- form buttons added with frm.add_custom_button ----

    private static string ButtonCss(string label) => $".page-head button[data-label=\"{Uri.EscapeDataString(label)}\"]";

    public bool HasButton(string label) => IsPresent(ButtonCss(label));

    public void ClickButton(string label) => Click(ButtonCss(label));

    public void Save()
    {
        Driver.FindElement(By.TagName("body")).SendKeys(Keys.Control + "s");
        WaitUntilIdle();
    }

    // ---- dialogs and toasts ----

    public (string Title, string Body) Dialog(TimeSpan? timeout = null)
    {
        var modal = FindVisible(".modal.show", timeout);
        return (modal.FindElement(By.CssSelector(".modal-title")).Text, modal.FindElement(By.CssSelector(".modal-body")).Text);
    }

    public void CloseDialog() =>
        // Escape closes the top-most Frappe dialog, even while its open animation is running
        WaitFor(d =>
        {
            if (!IsPresent(".modal.show")) return true;
            d.FindElement(By.TagName("body")).SendKeys(Keys.Escape);
            return false;
        }, "Dialog did not close");

    public IWebElement WaitForAlert(string text) =>
        WaitFor(d => d.FindElements(By.XPath(
                $"//*[@id='alert-container']//*[contains(@class,'alert')][contains(., {XPathLiteral(text)})]"))
            .FirstOrDefault(), $"No alert containing \"{text}\"")!;

    private static string XPathLiteral(string text) =>
        text.Contains('\'') ? $"concat('{text.Replace("'", "', \"'\", '")}')" : $"'{text}'";

    // ---- document values ----

    /// <summary>
    /// The document shown by the current route (/app/&lt;doctype&gt;/&lt;name&gt;), read from Frappe's
    /// client-side model, including unsaved edits. Avoids parsing formatted text such as "₹ 504.00",
    /// and unlike the cur_frm global it can't point at the previous form right after a route change.
    /// </summary>
    public JsonElement Doc() =>
        JsonDocument.Parse(WaitFor(_ => (string?)Js.ExecuteScript("""
            const [view, doctype, name = doctype] = frappe.get_route(); // single doctypes have no name in the route
            const doc = view === "Form" && locals[doctype] && locals[doctype][name];
            return doc && !doc.__islocal ? JSON.stringify(doc) : null;
            """), "No saved document is open")!).RootElement;

    public string? Text(string fieldname) =>
        Doc().TryGetProperty(fieldname, out var value) && value.ValueKind == JsonValueKind.String ? value.GetString() : null;

    public decimal Number(string fieldname) =>
        Doc().TryGetProperty(fieldname, out var value) && value.ValueKind == JsonValueKind.Number ? value.GetDecimal() : 0;

    protected object? Script(string script, params object[] args) => Js.ExecuteScript(script, args);
}
