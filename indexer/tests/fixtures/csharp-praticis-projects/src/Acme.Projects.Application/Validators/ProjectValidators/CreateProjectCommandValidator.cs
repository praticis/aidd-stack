using Acme.Projects.Application.Commands.ProjectCommands;
using Acme.Projects.Domain.Interfaces;
using FluentValidation;

namespace Acme.Projects.Application.Validators.ProjectValidators;

public class CreateProjectCommandValidator : AbstractValidator<CreateProjectCommand>
{
    public CreateProjectCommandValidator(IServiceProvider provider)
    {
        var projectRepository = provider.GetRequiredService<IProjectReadRepository>();

        RuleFor(r => r.Request)
            .NotNull();

        RuleFor(r => r.Request.Name)
            .NotEmpty()
                .WithErrorCode(ProjectValidationErrors.RequiredField.ErrorCode)
                .WithMessage(ProjectValidationErrors.RequiredField.ErrorMessage)
            .Must(name => !projectRepository.Exists(name))
                .WithErrorCode(ProjectValidationErrors.ProjectAlreadyExists.ErrorCode)
                .WithMessage(ProjectValidationErrors.ProjectAlreadyExists.ErrorMessage);

        RuleFor(r => r.Request.TodoIds)
            .NotEmpty()
                .WithErrorCode(ProjectValidationErrors.RequiredField.ErrorCode)
                .WithMessage(ProjectValidationErrors.RequiredField.ErrorMessage);
    }
}
