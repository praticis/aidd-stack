using Acme.Todos.Api.Application.Commands.ActivityCommands;
using Acme.Todos.Api.Domain.Interfaces.Repositories;
using FluentValidation;

namespace Acme.Todos.Api.Application.Validators.ActivityValidators;

public class RegisterActivityCommandValidator : AbstractValidator<RegisterActivityCommand>
{
    public RegisterActivityCommandValidator(IServiceProvider provider)
    {
        var activityRepository = provider.GetRequiredService<IActivityReadRepository>();

        RuleFor(r => r.Request)
            .NotNull();

        RuleFor(r => r.IdempotencyKey)
            .Must(idempotencyKey => activityRepository.IsUniqueKey(idempotencyKey))
            .WithErrorCode(ActivityValidationErrors.IdempotencyKeyConflict.ErrorCode)
            .WithMessage(ActivityValidationErrors.IdempotencyKeyConflict.ErrorMessage);

        RuleFor(r => r.Request.Title)
            .NotEmpty()
                .WithErrorCode(ActivityValidationErrors.RequiredField.ErrorCode)
                .WithMessage(ActivityValidationErrors.RequiredField.ErrorMessage);

        RuleFor(r => r.Request.Value)
            .GreaterThanOrEqualTo(0)
                .WithErrorCode(ActivityValidationErrors.ValueMustBePositive.ErrorCode)
                .WithMessage(ActivityValidationErrors.ValueMustBePositive.ErrorMessage);
    }
}
