import smtplib

from src.sender import send_email, send_email_with_diagnostics


def test_send_email_performs_tls_login_and_sends_html(mocker):
    mocker.patch("src.sender.GMAIL_ADDRESS", "sender@example.com")
    mocker.patch("src.sender.GMAIL_APP_PASSWORD", "app-password")
    smtp = mocker.patch("src.sender.smtplib.SMTP")
    server = smtp.return_value.__enter__.return_value

    assert send_email("Test subject", "<p>Test body</p>", "recipient@example.com")

    smtp.assert_called_once_with("smtp.gmail.com", 587)
    server.starttls.assert_called_once_with()
    server.login.assert_called_once()
    server.sendmail.assert_called_once()

    message = server.sendmail.call_args.args[2]
    assert "Test subject" in message
    assert "Test body" in message


def test_send_email_reports_missing_runtime_configuration(mocker):
    mocker.patch("src.sender.GMAIL_ADDRESS", "")
    mocker.patch("src.sender.GMAIL_APP_PASSWORD", "")
    smtp = mocker.patch("src.sender.smtplib.SMTP")

    success, detail = send_email_with_diagnostics("Test subject", "<p>Test body</p>", "recipient@example.com")

    assert not success
    assert detail == (
        "SMTP configuration is incomplete in the running backend process. "
        "GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set."
    )
    smtp.assert_not_called()


def test_send_email_reports_gmail_authentication_failure(mocker):
    mocker.patch("src.sender.GMAIL_ADDRESS", "sender@example.com")
    mocker.patch("src.sender.GMAIL_APP_PASSWORD", "app-password")
    smtp = mocker.patch("src.sender.smtplib.SMTP")
    smtp.return_value.__enter__.return_value.login.side_effect = smtplib.SMTPAuthenticationError(
        535, b"authentication failed"
    )

    success, detail = send_email_with_diagnostics("Test subject", "<p>Test body</p>", "recipient@example.com")

    assert not success
    assert detail == "SMTP authentication failed. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD."
