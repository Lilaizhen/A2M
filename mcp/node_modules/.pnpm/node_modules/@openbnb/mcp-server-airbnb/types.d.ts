declare module 'robots-parser' {
  interface RobotsParser {
    isAllowed(url: string, userAgent?: string): boolean;
  }

  function robotsParser(url: string, content: string): RobotsParser;
  
  export default robotsParser;
}
