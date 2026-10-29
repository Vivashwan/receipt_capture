using ReceiptCapture.E2E.Pages;
using ReceiptCapture.E2E.Support;

namespace ReceiptCapture.E2E.Tests;

[TestFixture, Order(1), Category("Smoke")]
public class LoginTests : UiTest
{
    [Test, Order(1)]
    public void RejectsAWrongPasswordAndStaysOnTheLoginPage()
    {
        var login = new LoginPage(Driver);
        login.Open();
        login.Submit(TestSettings.AdminUser, "not-the-password");

        Assert.That(login.WaitForError(), Does.Contain("Invalid Login"));
        Assert.That(Driver.Url, Does.Contain("/login"));
    }

    [Test, Order(2)]
    public void LogsInWithValidCredentialsAndOpensTheDesk()
    {
        new LoginPage(Driver).LoginAs(TestSettings.AdminUser, TestSettings.AdminPassword);

        Assert.That(Driver.Url, Does.Contain("/app"));
    }
}
