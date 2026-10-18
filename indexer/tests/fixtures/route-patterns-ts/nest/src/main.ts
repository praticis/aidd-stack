import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { excludePaths } from 'src/constants.js';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  // Every controller route of this package under /api, but the excluded ones (a list of another file).
  app.setGlobalPrefix('api', { exclude: excludePaths });
  await app.listen(3000);
}
bootstrap();
