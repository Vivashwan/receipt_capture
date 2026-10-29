using System.Text.Json;
using OpenQA.Selenium;
using ReceiptCapture.E2E.Support;

namespace ReceiptCapture.E2E.Pages;

public record SummaryRow(string? Supplier, string? SupplierName, int Receipts, int Invoiced, int NeedsAttention);

public class SummaryReportPage(IWebDriver driver) : DeskPage(driver)
{
    private string? _data;

    /// <summary>Opens the report with filters passed as route options in the URL.</summary>
    public void Open(IDictionary<string, string> filters)
    {
        var query = string.Join("&", filters.Select(f => $"{f.Key}={Uri.EscapeDataString(f.Value)}"));
        Driver.Navigate().GoToUrl($"{TestSettings.BaseUrl}/app/query-report/Receipt Capture Summary?{query}");

        // The report may run more than once while it applies saved and URL filters, so wait
        // until the filters match, nothing is loading, and the result has stopped changing.
        string? previous = null;
        var stableSince = DateTime.UtcNow;
        _data = WaitFor(_ =>
        {
            var state = (string?)Script("""
                const qr = frappe.query_report;
                if (!qr || !qr.data || qr.report_name !== "Receipt Capture Summary" || frappe.request.ajax_count) return null;
                const applied = qr.get_filter_values();
                const wanted = arguments[0];
                if (Object.keys(wanted).some((key) => String(applied[key]) !== String(wanted[key]))) return null;
                return JSON.stringify(qr.data);
                """, filters);
            if (state is null || state != previous)
            {
                previous = state;
                stableSince = DateTime.UtcNow;
                return null;
            }
            return DateTime.UtcNow - stableSince >= TimeSpan.FromSeconds(1) ? state : null;
        }, $"Report did not load with filters {JsonSerializer.Serialize(filters)}", TimeSpan.FromSeconds(30));
    }

    /// <summary>Rows as returned by the report.</summary>
    public IReadOnlyList<SummaryRow> Rows() =>
        JsonDocument.Parse(_data ?? throw new InvalidOperationException("Open the report first")).RootElement
            .EnumerateArray()
            .Select(r => new SummaryRow(
                Str(r, "supplier"), Str(r, "supplier_name"), Int(r, "receipts"), Int(r, "invoiced"), Int(r, "needs_attention")))
            .ToList();

    public IReadOnlyDictionary<string, string> SummaryCards() =>
        Driver.FindElements(By.CssSelector(".report-summary .summary-item"))
            .ToDictionary(
                card => card.FindElement(By.CssSelector(".summary-label")).Text,
                card => card.FindElement(By.CssSelector(".summary-value")).Text);

    private static string? Str(JsonElement row, string name) =>
        row.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;

    // SUM() comes back from MariaDB as a decimal, e.g. 1.0
    private static int Int(JsonElement row, string name) =>
        row.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.Number ? (int)v.GetDecimal() : 0;
}
