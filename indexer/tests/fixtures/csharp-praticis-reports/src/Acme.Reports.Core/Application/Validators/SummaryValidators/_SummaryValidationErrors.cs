using FluentValidation.Results;

namespace Acme.Reports.Core.Application.Validators.SummaryValidators;

public class SummaryValidationErrors
{
    public static readonly ValidationFailure SummaryNotExists = new () { ErrorCode = "SUMMARY_NOT_FOUND", ErrorMessage = "The '{PropertyName}' was not found with the provided information."};
}
