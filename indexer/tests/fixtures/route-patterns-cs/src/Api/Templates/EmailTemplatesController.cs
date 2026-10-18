using Microsoft.AspNetCore.Mvc;

namespace Api.Templates;

[Route("api/apps/{appId:notEmpty}/email-templates")]
public sealed class EmailTemplatesController : ChannelTemplatesController<EmailTemplate, EmailTemplateDto>
{
}

[Route("api/apps/{appId:notEmpty}/sms-templates")]
public sealed class SmsTemplatesController : ChannelTemplatesController<SmsTemplate, SmsTemplateDto>
{
    // its own: replaces the inherited one
    [HttpDelete("{code:notEmpty}/all")]
    public IActionResult DeleteTemplate(string appId, string code) => Ok();
}
