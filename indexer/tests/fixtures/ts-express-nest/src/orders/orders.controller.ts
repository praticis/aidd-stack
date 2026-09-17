import { Controller, Get, Post, Param } from '@nestjs/common';

@Controller('orders')
export class OrdersController {
  @Get(':id')
  findOne(@Param('id') id: string) { return id; }

  @Post()
  create() { return 1; }
}
