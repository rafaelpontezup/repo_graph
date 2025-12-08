# Rule 1
import pkg.a
import pkg.b as pb

# Rule 3
import pkg.sub1.m1 as mod_m1
import pkg.sub1.m2 as mod_m2

# Rule 2 (absolute modules)
from pkg import a
from pkg.sub2 import x, y
from pkg.sub2.x import func_x

# Rule 2 (relative from main — should behave like absolute)
from util import tool
