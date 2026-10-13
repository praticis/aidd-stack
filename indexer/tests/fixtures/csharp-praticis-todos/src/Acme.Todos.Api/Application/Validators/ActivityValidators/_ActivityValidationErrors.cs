using FluentValidation.Results;

namespace Acme.Todos.Api.Application.Validators.ActivityValidators;

public class ActivityValidationErrors
{
    public static readonly ValidationFailure RequiredField = new() { ErrorCode = "VALIDATION_FAILURE", ErrorMessage = "The field '{PropertyName}' is required and cannot be empty." };
    public static readonly ValidationFailure ValueMustBePositive = new() { ErrorCode = "VALIDATION_FAILURE", ErrorMessage = "The field '{PropertyName}' must be positive." };
    public static readonly ValidationFailure IdempotencyKeyConflict = new() { ErrorCode = "IDEMPOTENCY_CONFLICT", ErrorMessage = "This activity has already been processed." };
}
