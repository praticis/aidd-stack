import { Controller, Get, Post } from '@nestjs/common';
import { RouteKey } from '../enum.js';

// The prefix is an enum member of another file: GET /api/cats, POST /api/cats, GET /api/cats/{id}.
@Controller(RouteKey.Cats)
export class CatsController {
  @Get()
  findAll() {}

  @Post()
  create() {}

  @Get(':id')
  findOne() {}
}
