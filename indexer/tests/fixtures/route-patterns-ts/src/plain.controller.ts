import { Controller, Get } from '@nestjs/common';

// Another package than nest/: its setGlobalPrefix does not apply (GET /plain).
@Controller('plain')
export class PlainController {
  @Get()
  list() {}
}
