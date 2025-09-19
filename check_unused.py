import ast
import sys

def find_unused_variables(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        source = f.read()
    
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"语法错误: {e}")
        return
    
    # 收集所有定义的变量
    defined_vars = set()
    used_vars = set()
    
    class VarVisitor(ast.NodeVisitor):
        def visit_Name(self, node):
            if isinstance(node.ctx, ast.Store):
                defined_vars.add(node.id)
            elif isinstance(node.ctx, ast.Load):
                used_vars.add(node.id)
            self.generic_visit(node)
        
        def visit_FunctionDef(self, node):
            # 不检查函数参数
            for stmt in node.body:
                self.visit(stmt)
    
    visitor = VarVisitor()
    visitor.visit(tree)
    
    # 找出未使用的变量
    unused_vars = defined_vars - used_vars
    
    # 过滤掉一些特殊情况
    ignored_vars = {'_', '__name__', '__file__', '__doc__', '__package__'}
    unused_vars = unused_vars - ignored_vars
    
    if unused_vars:
        print("可能未使用的变量:")
        for var in sorted(unused_vars):
            print(f"  {var}")
    else:
        print("未发现未使用的变量")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python check_unused.py <filename>")
        sys.exit(1)
    
    find_unused_variables(sys.argv[1])
