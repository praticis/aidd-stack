package onboarding

import (
	"context"
	"net/http"
	"net/url"
)

const (
	onboardingsPath   = "/v1/onboardings"
	documentsSegment  = "/documents/"
	contentTypeHeader = "Content-Type"
	contentTypeJSON   = "application/json"
)

type Request struct {
	Method  string
	Path    string
	Headers map[string]string
	Body    any
}

type Response struct {
	StatusCode int
	Body       []byte
}

type Client interface {
	Do(ctx context.Context, req Request) (Response, error)
	GetJSON(ctx context.Context, path string, out any) error
}

type OnboardingClient struct {
	http Client
}

type ID struct{ v string }

func (i ID) Value() string { return i.v }

func (c *OnboardingClient) GetOnboardingSteps(ctx context.Context, onboardingID ID) error {
	path, err := url.JoinPath(onboardingsPath, onboardingID.Value(), "steps")
	if err != nil {
		return err
	}
	var envelope map[string]any
	return c.http.GetJSON(ctx, path, &envelope)
}

func (c *OnboardingClient) SubmitOnboarding(ctx context.Context, onboardingID ID, payload map[string]any) error {
	path, err := url.JoinPath(onboardingsPath, onboardingID.Value(), "submit")
	if err != nil {
		return err
	}
	_, err = c.http.Do(ctx, Request{
		Method:  http.MethodPost,
		Path:    path,
		Headers: map[string]string{contentTypeHeader: contentTypeJSON},
		Body:    payload,
	})
	return err
}

func (c *OnboardingClient) RegisterDocumentOCRReference(ctx context.Context, onboardingID ID, documentID string, payload map[string]any) error {
	path := onboardingsPath + "/" + onboardingID.Value() + documentsSegment + documentID + "/ocr-reference"
	_, err := c.http.Do(ctx, Request{
		Method:  http.MethodPut,
		Path:    path,
		Headers: map[string]string{contentTypeHeader: contentTypeJSON},
		Body:    payload,
	})
	return err
}

func (c *OnboardingClient) CreateLivenessSession(ctx context.Context, documentNumber string) error {
	_, err := c.http.Do(ctx, Request{
		Method: http.MethodPost,
		Path:   "/v1/liveness/session",
		Body:   map[string]string{"documentNumber": documentNumber},
	})
	return err
}

func (c *OnboardingClient) CreateOnboarding(ctx context.Context, payload map[string]any) error {
	_, err := c.http.Do(ctx, Request{
		Method: http.MethodPost,
		Path:   onboardingsPath,
		Body:   payload,
	})
	return err
}
