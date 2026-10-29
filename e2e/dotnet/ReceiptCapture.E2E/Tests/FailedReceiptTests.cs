using ReceiptCapture.E2E.Pages;
using ReceiptCapture.E2E.Support;

namespace ReceiptCapture.E2E.Tests;

[TestFixture, Order(4)]
public class FailedReceiptTests : UiTest
{
    private ReceiptCapturePage Receipt => new(Driver);

    protected override (string, string)? LoginAs => (TestSettings.Reviewer, TestSettings.UserPassword);

    [Test, Order(1)]
    public void FailsWithAReasonTheUserCanActOn()
    {
        Receipt.Upload("blank.png");

        Assert.That(Receipt.WaitForExtraction(), Is.EqualTo("Failed"));
        Assert.Multiple(() =>
        {
            Assert.That(Receipt.Headline, Does.Contain("No readable text"));
            Assert.That(Receipt.HasButton("Re-run Extraction"), Is.True);
            Assert.That(Receipt.HasButton("Create Purchase Invoice"), Is.False);
        });
    }

    [Test, Order(2)]
    public void LetsTheUserKeyInLinesByHandWithTotalsKeptInSync()
    {
        var first = Receipt.AddRow();
        Receipt.SetCell(first, "description", "Printer paper");
        Receipt.SetCell(first, "qty", 2);
        Receipt.SetCell(first, "rate", 150);
        var second = Receipt.AddRow();
        Receipt.SetCell(second, "description", "Courier");
        Receipt.SetCell(second, "rate", 60);

        Assert.That(Receipt.Number("lines_total"), Is.EqualTo(360m));
        Assert.That(Receipt.LineItems().Select(line => line.Description), Is.EqualTo(new[] { "Printer paper", "Courier" }));
    }

    [Test, Order(3)]
    public void WarnsWhenItemsAndTaxDontAddUpToTheTotal()
    {
        Receipt.SetField("tax_amount", 18);
        Receipt.SetField("total_amount", 500);

        Receipt.WaitForAlert("don't match the total");
    }

    [Test, Order(4)]
    public void SavesTheManualCorrections()
    {
        Receipt.SetField("total_amount", 378);
        Receipt.Save();

        Receipt.Open(Receipt.Name);
        Assert.Multiple(() =>
        {
            Assert.That(Receipt.Number("lines_total"), Is.EqualTo(360m));
            Assert.That(Receipt.Number("total_amount"), Is.EqualTo(378m));
            Assert.That(Receipt.RowCount, Is.EqualTo(2));
        });
    }
}
