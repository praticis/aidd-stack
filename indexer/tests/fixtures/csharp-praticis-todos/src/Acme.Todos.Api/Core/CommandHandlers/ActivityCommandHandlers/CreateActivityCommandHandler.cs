using Acme.Todos.Api.Application.Commands.ActivityCommands;
using Acme.Todos.Api.Domain.Interfaces.Repositories;
using Acme.Todos.Api.Domain.Models;
using Acme.Todos.Contracts.Events.ActivityEvents;
using Acme.Todos.Contracts.Objects;
using Acme.Todos.Contracts.Responses.ActivityResponses;
using Acme.Shared.Bus.Abstractions;

namespace Acme.Todos.Api.Core.CommandHandlers.ActivityCommandHandlers;

public class CreateActivityCommandHandler(IServiceProvider provider) : ICommandHandler<RegisterActivityCommand, RegisterActivityResponse>
{
    private readonly IServiceBus _serviceBus = provider.GetRequiredService<IServiceBus>();
    private readonly INotificationStore _store = provider.GetRequiredService<INotificationStore>();
    private IActivityRepository _activityRepository = provider.GetRequiredService<IActivityRepository>();

    public async Task<RegisterActivityResponse?> Handle(RegisterActivityCommand command, CancellationToken cancellationToken)
    {
        var request = command.Request;
        var idempotencyKey = command.IdempotencyKey;
        var registerDate = request.Date.GetValueOrDefault(DateTime.UtcNow);

        var activity = new ActivityModel(idempotencyKey, request.Title, request.Value, registerDate, request.TagId);

        await this._activityRepository.CreateAsync(activity, cancellationToken);

        if (this._store.HasNotifications())
            return default;

        var @event = GenerateActivityWasCreatedEvent(activity);

        await this._serviceBus.PublishAsync(@event, cancellationToken);

        var response = GenerateResponse(activity);

        return response;
    }

    private static ActivityWasCreatedEvent GenerateActivityWasCreatedEvent(ActivityModel activity)
    {
        var @event = new ActivityWasCreatedEvent
        {
            Activity = new ActivityObject
            {
                ActivityId = activity.Id,
                TagId = activity.TagId,
                IdempotencyKey = activity.IdempotencyKey,
                Title = activity.Title,
                Value = activity.Value,
                CreatedAt = activity.CreatedAt,
                OccurredAt = activity.OccurredAt
            }
        };

        return @event;
    }

    private static RegisterActivityResponse GenerateResponse(ActivityModel activity)
    {
        var response = new RegisterActivityResponse
        {
            ActivityId = activity.Id,
            IdempotencyKey = activity.IdempotencyKey,
            Title = activity.Title,
            Value = activity.Value,
            TagId = activity.TagId,
            CreatedAt = activity.CreatedAt
        };

        return response;
    }

    public void Dispose()
    {
        this._activityRepository?.Dispose();
        this._activityRepository = null;
    }
}
