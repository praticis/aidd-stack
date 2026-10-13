using Acme.Todos.Api.Application.Commands.TodoCommands;
using Acme.Todos.Api.Domain.Interfaces.Repositories;
using FluentValidation;

namespace Acme.Todos.Api.Application.Validators.TodoValidators;

public class CreateTodoCommandValidator : AbstractValidator<CreateTodoCommand>
{
    public CreateTodoCommandValidator(IServiceProvider provider)
    {
        var todoRepository = provider.GetRequiredService<ITodoReadRepository>();

        RuleFor(r => r.Request)
            .NotNull();

        RuleFor(r => r.Request.Name)
            .NotEmpty()
                .WithErrorCode(TodoValidationErrors.RequiredField.ErrorCode)
                .WithMessage(TodoValidationErrors.RequiredField.ErrorMessage)
            .MinimumLength(5)
                .WithErrorCode(TodoValidationErrors.InvalidField.ErrorCode)
                .WithMessage(TodoValidationErrors.InvalidField.ErrorMessage)
            .Must(accName => todoRepository.NotExists(accName))
                .WithErrorCode(TodoValidationErrors.TodoAlreadyExists.ErrorCode)
                .WithMessage(TodoValidationErrors.TodoAlreadyExists.ErrorMessage);
    }
}
