package main

import (
	"fmt"

	"github.com/gin-gonic/gin"
)

const SchemasPath string = "schemas"

// kratos: a constant naming one segment, formatted into the path — GET /schemas and GET /schemas/{id};
// a verb whose argument the code does not hold stays a parameter: GET /tenants/{param}/schemas.
func main() {
	r := gin.New()
	r.GET(fmt.Sprintf("/%s", SchemasPath), listSchemas)
	r.GET(fmt.Sprintf("/%s/:id", SchemasPath), getSchema)
	r.GET(fmt.Sprintf("/tenants/%s/%s", tenantID(), SchemasPath), listSchemas)
	r.Run(":4433")
}

func tenantID() string { return "t" }

func listSchemas(c *gin.Context) {}

func getSchema(c *gin.Context) {}
