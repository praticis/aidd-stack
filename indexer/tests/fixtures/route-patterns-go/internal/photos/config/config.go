package config

const ApiUri = "/api/v1"

type Config struct {
	siteUrl string
}

func (c *Config) SiteUrl() string { return c.siteUrl }

func (c *Config) BasePath() string { return "/photos" }

// BaseUri returns the path under the site's base path, when one is configured.
func (c *Config) BaseUri(res string) string {
	if c.SiteUrl() == "" {
		return res
	}

	return c.BasePath() + res
}
