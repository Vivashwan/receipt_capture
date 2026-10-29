using System.Text.RegularExpressions;
using OpenQA.Selenium;
using ReceiptCapture.E2E.Support;

namespace ReceiptCapture.E2E.Pages;

public record LineItem(string Description, decimal Qty, decimal Rate, decimal Amount);

public partial class ReceiptCapturePage(IWebDriver driver) : DeskPage(driver)
{
    private const string Rows = ".frappe-control[data-fieldname=\"items\"] .grid-body .grid-row";
    private const string AttachButton = "button.btn-attach[data-fieldname=\"receipt_image\"]";
    // Statuses after which the background job has finished
    private static readonly string[] Finished = ["Extracted", "Needs Review", "Failed"];

    public string Name => Text("name")!;

    public void OpenNew()
    {
        GoTo("receipt-capture/new");
        FindVisible(AttachButton);
    }

    public void Open(string name)
    {
        GoTo($"receipt-capture/{Uri.EscapeDataString(name)}");
        WaitFor(_ => Text("name") == name, $"Receipt {name} did not open");
    }

    /// <summary>Uploads a fixture through the standard file uploader dialog.</summary>
    public void AttachReceipt(string fixture)
    {
        Click(AttachButton);
        FindVisible(".modal.show");
        // The uploader's <input type=file> is hidden; ChromeDriver still accepts a path for it
        Find(".modal.show input[type=file]").SendKeys(Path.Combine(TestSettings.FixturesDir, fixture));
        Click(".modal.show .btn-modal-primary");
        WaitFor(_ => !IsPresent(".modal.show"), "Upload dialog did not close", TimeSpan.FromSeconds(30));
        Find(".frappe-control[data-fieldname=\"receipt_image\"] a.attached-file-link[href*=\"/files/\"]");
    }

    /// <summary>Attaches and saves a new receipt; returns its name (e.g. RCPT-2026-00001).</summary>
    public string Upload(string fixture)
    {
        OpenNew();
        AttachReceipt(fixture);
        Save();
        WaitFor(d => SavedReceiptUrl().IsMatch(d.Url), "Receipt was not saved", TimeSpan.FromSeconds(30));
        return Name;
    }

    /// <summary>
    /// Waits for the background job to finish. The page is not reloaded here: the form must
    /// update itself from the realtime event the worker publishes.
    /// </summary>
    public string WaitForExtraction()
    {
        var status = WaitFor(_ => Finished.Contains(Status) ? Status : null, "Extraction did not finish", TestSettings.ExtractionTimeout)!;
        WaitUntilIdle();
        return status;
    }

    /// <summary>Message set with frm.dashboard.set_headline_alert, shown above the form.</summary>
    public string Headline => Visible(".form-message-container .form-message")?.Text ?? "";

    // ---- line items grid ----

    private static string RowCss(int idx) => $"{Rows}[data-idx=\"{idx}\"]";

    public int RowCount => Driver.FindElements(By.CssSelector(Rows)).Count;

    /// <summary>Line items from the form model (a row being edited shows inputs, not text).</summary>
    public IReadOnlyList<LineItem> LineItems() =>
        Doc().GetProperty("items").EnumerateArray()
            .Select(row => new LineItem(
                row.TryGetProperty("description", out var d) ? d.GetString() ?? "" : "",
                row.TryGetProperty("qty", out var q) ? q.GetDecimal() : 0,
                row.TryGetProperty("rate", out var r) ? r.GetDecimal() : 0,
                row.TryGetProperty("amount", out var a) ? a.GetDecimal() : 0))
            .ToList();

    /// <summary>Adds an empty line and returns its row number.</summary>
    public int AddRow()
    {
        var idx = RowCount + 1;
        Click(".frappe-control[data-fieldname=\"items\"] .grid-add-row");
        Find(RowCss(idx));
        return idx;
    }

    public void SetCell(int idx, string fieldname, object value)
    {
        var input = $"{RowCss(idx)} input[data-fieldname=\"{fieldname}\"]";
        // A new row opens in edit mode; an existing one needs a click on the cell first
        if (!IsPresent(input)) Click($"{RowCss(idx)} .grid-static-col[data-fieldname=\"{fieldname}\"]");
        TypeInto(input, value);
    }

    public void SetField(string fieldname, object value) =>
        TypeInto($".frappe-control[data-fieldname=\"{fieldname}\"] input", value);

    public void CreatePurchaseInvoice()
    {
        ClickButton("Create Purchase Invoice");
        WaitFor(d => PurchaseInvoiceUrl().IsMatch(d.Url), "Did not open the new Purchase Invoice", TimeSpan.FromSeconds(60));
        WaitUntilIdle();
    }

    [GeneratedRegex(@"/receipt-capture/(?!new)[^/]+$")]
    private static partial Regex SavedReceiptUrl();

    [GeneratedRegex(@"/purchase-invoice/[^/]+$")]
    private static partial Regex PurchaseInvoiceUrl();
}
