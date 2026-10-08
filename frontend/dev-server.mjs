import { createServer } from 'vite'

const server = await createServer({
  configLoader: 'native',
  server: { host: '127.0.0.1' },
})
await server.listen()
server.printUrls()
