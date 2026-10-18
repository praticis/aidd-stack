import { Controller, Get } from '@nestjs/common';

@Controller()
export class AppController {
  @Get('health')             // excluded from the global prefix: GET /health
  health() {}

  @Get('docs/openapi.json')  // excluded by a wildcard: GET /docs/openapi.json
  openapi() {}

  @Get(['ping', 'status'])   // two paths: GET /api/ping, GET /api/status
  ping() {}
}
