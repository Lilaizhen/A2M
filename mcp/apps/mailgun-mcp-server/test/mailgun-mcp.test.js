import { jest } from '@jest/globals';
import * as serverModule from '../src/mailgun-mcp.js';

// Disable console.error during tests
const originalConsoleError = console.error;
console.error = jest.fn();

// Override process.exit during tests
const originalProcessExit = process.exit;
process.exit = jest.fn();

describe('Mailgun MCP Server', () => {
  // Focus on testing the pure utility functions that don't need mocks
  describe('processPathParameters()', () => {
    test('replaces path parameters with values', () => {
      const path = '/v3/{domain_name}/messages';
      const operation = {
        parameters: [
          {
            name: 'domain_name',
            in: 'path',
            required: true
          }
        ]
      };
      const params = { domain_name: 'example.com', to: 'test@example.com' };
      
      const result = serverModule.processPathParameters(path, operation, params);
      
      expect(result.actualPath).toBe('/v3/example.com/messages');
      expect(result.remainingParams).toEqual({ to: 'test@example.com' });
    });
    
    test('throws error if required path parameter is missing', () => {
      const path = '/v3/{domain_name}/messages';
      const operation = {
        parameters: [
          {
            name: 'domain_name',
            in: 'path',
            required: true
          }
        ]
      };
      const params = { to: 'test@example.com' };
      
      expect(() => {
        serverModule.processPathParameters(path, operation, params);
      }).toThrow(/required path parameter.*missing/i);
    });
  });

  describe('separateParameters()', () => {
    test('separates query and body parameters', () => {
      const params = { 
        limit: 10, 
        page: 1,
        to: 'test@example.com',
        from: 'sender@example.com'
      };
      
      const operation = {
        parameters: [
          { name: 'limit', in: 'query' },
          { name: 'page', in: 'query' }
        ]
      };
      
      const result = serverModule.separateParameters(params, operation, 'POST');
      
      expect(result.queryParams).toEqual({ limit: 10, page: 1 });
      expect(result.bodyParams).toEqual({ 
        to: 'test@example.com',
        from: 'sender@example.com'
      });
    });
    
    test('moves all params to query for GET requests', () => {
      const params = { 
        limit: 10, 
        page: 1,
        to: 'test@example.com',
        from: 'sender@example.com'
      };
      
      const operation = {
        parameters: [
          { name: 'limit', in: 'query' },
          { name: 'page', in: 'query' }
        ]
      };
      
      const result = serverModule.separateParameters(params, operation, 'GET');
      
      expect(result.queryParams).toEqual({ 
        limit: 10, 
        page: 1,
        to: 'test@example.com',
        from: 'sender@example.com'
      });
      expect(result.bodyParams).toEqual({});
    });
  });

  describe('appendQueryString()', () => {
    test('appends query parameters to path', () => {
      const path = '/v3/domains';
      const queryParams = { limit: 10, skip: 0 };
      
      const result = serverModule.appendQueryString(path, queryParams);
      
      expect(result).toBe('/v3/domains?limit=10&skip=0');
    });
    
    test('returns original path if no query parameters', () => {
      const path = '/v3/domains';
      const queryParams = {};
      
      const result = serverModule.appendQueryString(path, queryParams);
      
      expect(result).toBe('/v3/domains');
    });
  });

  // Clean up after all tests
  afterAll(() => {
    console.error = originalConsoleError;
    process.exit = originalProcessExit;
  });
});

describe('openapiToZod()', () => {
    test('converts string schema correctly', () => {
      const schema = { type: 'string', description: 'A test string' };
      const result = serverModule.openapiToZod(schema, {});
      
      expect(result._def.typeName).toBe('ZodString');
      expect(result._def.description).toBe('A test string');
    });
    
    test('converts enum schema correctly', () => {
      const schema = { type: 'string', enum: ['yes', 'no', 'maybe'] };
      const result = serverModule.openapiToZod(schema, {});
      
      expect(result._def.typeName).toBe('ZodEnum');
      expect(result._def.values).toEqual(['yes', 'no', 'maybe']);
    });
    
    test('converts number schema with constraints', () => {
      const schema = { 
        type: 'number', 
        minimum: 1, 
        maximum: 100,
        description: 'A constrained number' 
      };
      const result = serverModule.openapiToZod(schema, {});
      
      expect(result._def.typeName).toBe('ZodNumber');
        // Check for min constraint
        expect(result._def.checks.some(check => 
            check.kind === 'min' && check.value === 1
        )).toBe(true);
        
        // Check for max constraint
        expect(result._def.checks.some(check => 
            check.kind === 'max' && check.value === 100
        )).toBe(true);
    });
    
    test('resolves references correctly', () => {
      const schema = { $ref: '#/components/schemas/TestType' };
      const fullSpec = {
        components: {
          schemas: {
            TestType: { type: 'string', description: 'Referenced type' }
          }
        }
      };
      
      const result = serverModule.openapiToZod(schema, fullSpec);
      
      expect(result._def.typeName).toBe('ZodString');
      expect(result._def.description).toBe('Referenced type');
    });
  });
  
  describe('getOperationDetails()', () => {
    test('returns operation details for valid path and method', () => {
      const openApiSpec = {
        paths: {
          '/test/path': {
            get: {
              operationId: 'getTest',
              summary: 'Test operation'
            }
          }
        }
      };
      
      const result = serverModule.getOperationDetails(openApiSpec, 'get', '/test/path');
      
      expect(result).toEqual({
        operation: {
          operationId: 'getTest',
          summary: 'Test operation'
        },
        operationId: 'get--test-path'
      });
    });
    
    test('returns null for invalid path', () => {
      const openApiSpec = {
        paths: {
          '/test/path': {
            get: {
              operationId: 'getTest',
              summary: 'Test operation'
            }
          }
        }
      };
      
      const result = serverModule.getOperationDetails(openApiSpec, 'get', '/nonexistent/path');
      
      expect(result).toBeNull();
    });
    
    test('returns null for invalid method', () => {
      const openApiSpec = {
        paths: {
          '/test/path': {
            get: {
              operationId: 'getTest',
              summary: 'Test operation'
            }
          }
        }
      };
      
      const result = serverModule.getOperationDetails(openApiSpec, 'post', '/test/path');
      
      expect(result).toBeNull();
    });
  });
  
  describe('resolveReference()', () => {
    test('resolves reference path correctly', () => {
      const openApiSpec = {
        components: {
          schemas: {
            TestSchema: { type: 'string', description: 'Test schema' }
          }
        }
      };
      
      const result = serverModule.resolveReference('#/components/schemas/TestSchema', openApiSpec);
      
      expect(result).toEqual({ type: 'string', description: 'Test schema' });
    });
    
    test('handles nested reference path', () => {
      const openApiSpec = {
        components: {
          schemas: {
            Parent: {
              NestedType: { type: 'number', minimum: 0 }
            }
          }
        }
      };
      
      const result = serverModule.resolveReference('#/components/schemas/Parent/NestedType', openApiSpec);
      
      expect(result).toEqual({ type: 'number', minimum: 0 });
    });
});
  
