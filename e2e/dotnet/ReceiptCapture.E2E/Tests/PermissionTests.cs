using ReceiptCapture.E2E.Pages;
using ReceiptCapture.E2E.Support;

namespace ReceiptCapture.E2E.Tests;

[TestFixture, Order(6)]
public class AccountsUserPermissionTests : UiTest
{
    protected override (string, string)? LoginAs => (TestSettings.Reviewer, TestSettings.UserPassword);

    [Test]
    public void CanReadTheAISettingsButNotTestTheConnection()
    {
        var settings = new ReceiptAISettingsPage(Driver);
        settings.Open();

        Assert.That(settings.Text("model"), Is.Not.Null.And.Not.Empty);
        Assert.That(settings.HasButton(ReceiptAISettingsPage.TestConnection), Is.False);
    }
}

[TestFixture, Order(7)]
public class NoAccessPermissionTests : UiTest
{
    protected override (string, string)? LoginAs => (TestSettings.NoAccessUser, TestSettings.UserPassword);

    [Test]
    public void IsNotShownTheReceiptList()
    {
        var page = new DeskPage(Driver);
        page.GoTo("receipt-capture");

        Assert.That(page.Dialog().Title, Is.EqualTo("Not permitted"));
        Assert.That(page.IsPresent(".list-row"), Is.False);
    }
}
