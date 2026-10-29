using OpenQA.Selenium;

namespace ReceiptCapture.E2E.Pages;

public class ReceiptAISettingsPage(IWebDriver driver) : DeskPage(driver)
{
    public const string TestConnection = "Test Ollama Connection";

    public void Open()
    {
        GoTo("receipt-ai-settings");
        FindVisible(".frappe-control[data-fieldname=\"ollama_url\"]");
    }

    /// <summary>Clicks "Test Ollama Connection" and returns the resulting dialog.</summary>
    public (string Title, string Body) TestOllamaConnection()
    {
        ClickButton(TestConnection);
        // First call may load the model into memory
        return Dialog(TimeSpan.FromMinutes(2));
    }
}
