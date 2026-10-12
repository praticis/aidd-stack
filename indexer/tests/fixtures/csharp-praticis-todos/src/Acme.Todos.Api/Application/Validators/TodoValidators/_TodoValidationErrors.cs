using FluentValidation.Results;

namespace Acme.Todos.Api.Application.Validators.TodoValidators;

public static class TodoValidationErrors
{
    public static readonly ValidationFailure RequiredField = new() { ErrorCode = "VALIDATION_FAILURE", ErrorMessage = "The field '{PropertyName}' is required and cannot be empty." };
    public static readonly ValidationFailure InvalidField = new() { ErrorCode = "VALIDATION_FAILURE", ErrorMessage = "The field '{PropertyName}' must have at least {MinLength} characters." };
    public static readonly ValidationFailure TodoAlreadyExists = new() { ErrorCode = "TODO_NAME_CONFLICT", ErrorMessage = "The '{PropertyName}' already exists." };
}
