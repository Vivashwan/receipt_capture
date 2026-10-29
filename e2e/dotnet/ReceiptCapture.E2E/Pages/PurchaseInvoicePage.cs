using OpenQA.Selenium;

namespace ReceiptCapture.E2E.Pages;

public record InvoiceItem(string ItemCode, string Description, decimal Amount);

public record InvoiceDetails(string Name, int DocStatus, string Supplier, decimal GrandTotal, decimal TotalTaxes, IReadOnlyList<InvoiceItem> Items);

public class PurchaseInvoicePage(IWebDriver driver) : DeskPage(driver)
{
    public InvoiceDetails Details()
    {
        var doc = Doc();
        var doctype = doc.GetProperty("doctype").GetString();
        if (doctype != "Purchase Invoice") throw new InvalidOperationException($"Expected a Purchase Invoice, got {doctype}");

        return new InvoiceDetails(
            doc.GetProperty("name").GetString()!,
            doc.GetProperty("docstatus").GetInt32(),
            doc.GetProperty("supplier").GetString()!,
            doc.GetProperty("grand_total").GetDecimal(),
            doc.GetProperty("total_taxes_and_charges").GetDecimal(),
            doc.GetProperty("items").EnumerateArray()
                .Select(i => new InvoiceItem(
                    i.GetProperty("item_code").GetString()!,
                    i.GetProperty("description").GetString()!,
                    i.GetProperty("amount").GetDecimal()))
                .ToList());
    }
}
