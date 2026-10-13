using FluentValidation.Results;

namespace Acme.Projects.Application.Validators.ProjectValidators;

public static class ProjectValidationErrors
{
    public static readonly ValidationFailure RequiredField = new() { ErrorCode = "VALIDATION_FAILURE", ErrorMessage = "The field '{PropertyName}' is required and cannot be empty." };
    public static readonly ValidationFailure ProjectAlreadyExists = new() { ErrorCode = "PROJECT_NAME_CONFLICT", ErrorMessage = "The '{PropertyName}' already exists." };
}
