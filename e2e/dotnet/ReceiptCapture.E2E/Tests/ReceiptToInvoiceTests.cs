using ReceiptCapture.E2E.Pages;
using ReceiptCapture.E2E.Support;

namespace ReceiptCapture.E2E.Tests;

/// <summary>
/// One user journey, in order. The fixture is a tilted, noisy photo of:
/// RICE 320.00 / DAL 160.00 / GST 24.00 / TOTAL 504.00
/// </summary>
[TestFixture, Order(3)]
public class ReceiptToInvoiceTests : UiTest
{
    private string _receiptName = null!;

    protected override (string, string)? LoginAs => (TestSettings.Reviewer, TestSettings.UserPassword);

    [Test, Order(1)]
    public void UploadsAReceiptPhotoAndQueuesExtraction()
    {
        var receipt = new ReceiptCapturePage(Driver);
        _receiptName = receipt.Upload("receipt.png");

        Assert.That(_receiptName, Does.StartWith("RCPT-"));
        Assert.That(receipt.Status, Is.EqualTo("Processing"));
        Assert.That(receipt.Headline, Does.Contain("Reading the receipt"));
    }

    [Test, Order(2)]
    public void UpdatesTheOpenFormLiveWhenTheBackgroundJobFinishes()
    {
        var receipt = new ReceiptCapturePage(Driver);

        var status = receipt.WaitForExtraction();

        Assert.That(status, Is.AnyOf("Extracted", "Needs Review"));
        receipt.WaitForAlert("Extraction finished");
    }

    [Test, Order(3)]
    public void FillsVendorLineItemsTaxAndTotalFromThePhoto()
    {
        var receipt = new ReceiptCapturePage(Driver);
        var descriptions = string.Join(" | ", receipt.LineItems().Select(line => line.Description.ToUpperInvariant()));

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Text("supplier_name"), Does.Contain("annapurna").IgnoreCase);
            Assert.That(receipt.Number("total_amount"), Is.EqualTo(504m));
            Assert.That(receipt.Number("tax_amount"), Is.EqualTo(24m));
            Assert.That(descriptions, Does.Contain("RICE").And.Contain("DAL"));
            Assert.That(descriptions, Does.Not.Contain("TOTAL").And.Not.Contain("GST"), "summary or tax rows leaked into the items");
        });
    }

    [Test, Order(4)]
    public void CreatesADraftPurchaseInvoiceWithTheReceiptsAmounts()
    {
        new ReceiptCapturePage(Driver).CreatePurchaseInvoice();

        var invoice = new PurchaseInvoicePage(Driver);
        var details = invoice.Details();

        Assert.Multiple(() =>
        {
            Assert.That(invoice.Status, Is.EqualTo("Draft"));
            Assert.That(details.DocStatus, Is.Zero, "invoices are left as drafts for an accountant to submit");
            Assert.That(details.GrandTotal, Is.EqualTo(504m));
            Assert.That(details.TotalTaxes, Is.EqualTo(24m));
            Assert.That(details.Supplier, Is.Not.Empty, "a supplier is matched or created");
            Assert.That(details.Items.Select(i => i.ItemCode), Is.All.EqualTo("Receipt Expense"));
        });
    }

    [Test, Order(5)]
    public void MarksTheReceiptInvoicedAndLocksIt()
    {
        var receipt = new ReceiptCapturePage(Driver);
        receipt.Open(_receiptName);

        Assert.Multiple(() =>
        {
            Assert.That(receipt.Status, Is.EqualTo("Invoiced"));
            Assert.That(receipt.Text("purchase_invoice"), Is.Not.Null.And.Not.Empty);
            Assert.That(receipt.HasButton("Open Purchase Invoice"), Is.True);
            Assert.That(receipt.HasButton("Create Purchase Invoice"), Is.False, "can't invoice twice");
            Assert.That(receipt.HasButton("Re-run Extraction"), Is.False, "can't overwrite an invoiced receipt");
        });
    }
}
