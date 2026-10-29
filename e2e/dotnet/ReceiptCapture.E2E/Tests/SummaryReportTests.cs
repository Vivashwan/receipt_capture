using ReceiptCapture.E2E.Pages;
using ReceiptCapture.E2E.Support;

namespace ReceiptCapture.E2E.Tests;

[TestFixture, Order(5)]
public class SummaryReportTests : UiTest
{
    private static readonly string Today = DateTime.Now.ToString("yyyy-MM-dd");

    protected override (string, string)? LoginAs => (TestSettings.Reviewer, TestSettings.UserPassword);

    [Test]
    public void AggregatesReceiptsPerSupplierWithInvoicedAndPendingAmounts()
    {
        var report = new SummaryReportPage(Driver);
        report.Open(new Dictionary<string, string> { ["from_date"] = $"{DateTime.Now.Year}-01-01", ["to_date"] = Today });

        var annapurna = report.Rows().FirstOrDefault(r => r.SupplierName?.Contains("annapurna", StringComparison.OrdinalIgnoreCase) == true);

        Assert.That(annapurna, Is.Not.Null, "no Annapurna row");
        Assert.Multiple(() =>
        {
            Assert.That(annapurna!.Receipts, Is.GreaterThanOrEqualTo(1));
            Assert.That(annapurna.Invoiced, Is.GreaterThanOrEqualTo(1), "the receipt invoiced in the main flow is counted");
            Assert.That(int.Parse(report.SummaryCards()["Receipts"]), Is.GreaterThanOrEqualTo(1));
        });
    }

    [Test]
    public void StillShowsFailedReceiptsWhichHaveNoBillDateInsideADateRange()
    {
        var report = new SummaryReportPage(Driver);
        report.Open(new Dictionary<string, string> { ["from_date"] = Today, ["to_date"] = Today, ["status"] = "Failed" });

        Assert.That(report.Rows().Sum(r => r.Receipts), Is.GreaterThanOrEqualTo(1));
        Assert.That(report.SummaryCards()["Needs Attention"], Is.Not.EqualTo("0"));
    }
}
