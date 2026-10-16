using Microsoft.AspNetCore.Mvc;

namespace Api.Templates;

// Not routable by itself: every action lives under each derived controller's route (notifo).
public abstract class ChannelTemplatesController<T, TDto> : ControllerBase where T : class
{
    [HttpGet]
    public IActionResult GetTemplates(string appId) => Ok();

    [HttpGet("{id:notEmpty}")]
    public IActionResult GetTemplate(string appId, string id) => Ok();

    [HttpDelete("{code:notEmpty}")]
    public IActionResult DeleteTemplate(string appId, string code) => Ok();
}
