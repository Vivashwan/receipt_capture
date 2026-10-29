using ReceiptCapture.E2E.Pages;
using ReceiptCapture.E2E.Support;

namespace ReceiptCapture.E2E.Tests;

[TestFixture, Order(2), Category("Smoke")]
public class SettingsTests : UiTest
{
    protected override (string, string)? LoginAs => (TestSettings.AdminUser, TestSettings.AdminPassword);

    [Test]
    public void ReportsThatTheLocalModelIsReachable()
    {
        var settings = new ReceiptAISettingsPage(Driver);
        settings.Open();
        var model = settings.Text("model");

        var (title, body) = settings.TestOllamaConnection();

        Assert.Multiple(() =>
        {
            Assert.That(title, Is.EqualTo("Connected"));
            Assert.That(body, Does.Contain(model));
        });
        settings.CloseDialog();
    }
}
