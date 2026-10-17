import { Controller, Get } from '@nestjs/common';

@Controller({ path: 'dogs', version: '1' })
export class DogsController {
  @Get()
  list() {}
}
