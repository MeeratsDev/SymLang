# SYMLANG DOCUMENTATION

Welcome to SYMLANG, a language designed for the funnies and to make you hate your life.

### I: Declarations

**Variables** *($)*:
Variables are mutable variables that can be either dynamically *or* statically typed, they can be altered after declaration as so: `$myVar1 = $myVar2` (this snippet sets *myVar1* to the value of *myVar2*).

**Constants** *(c$)*:
Constants are immutable variables that **must** be given a type on creation.

**Classes** *(@)*:
Classes act like they do in any other language, they can have properties, methods, and can contain functions & variables. 

**Functions** *(#)*:
Functions can be given parameters, contain logic, and return values.

``` 
$x = i(10); // Creates a variable of type "integer" and assigns it a value of 10

c$x = i(10); // Creates a constant variable that it immutable.

@ MyClass {} // creats an empty class named "MyClass"

# myFunc (params) {} // creates an empty function named "myFunc"
```


### II: Data Types

Booleans = true | false
Floats = 0.0 
Interger = 0
Strings = ""
Arrays = []
Hashmaps = {}

All data types are assigned with inital().
```
$x = b(True); // creates a boolean variable and sets it to True

$x = f(10.0); // creates a float and sets it to 10.0

$x = i(10); // creates an integer and sets it to 10

$x = s("Hello World!") // creates a string and sets it to "Hello World!"

$x = a([]) // creates an empty array

$x = h({}) // creates an empty hashmap
```

### III: Statements

All statements are replaced with a symbol, this is for ease of use when quickly prototyping. e.g.
```
if x == 1:
	pass
	
becomes ->

? ($x == 1) {
	return;
}
```
#### All Statements:
"if statements" are called with 
```
? (args) {
	return;
}
```
"else statements" are called with
```
~ (args) {
	return;
}
```
"else if statements" are called with
```
~? (args) {
	return;
}
```
"when statements" are called with
```
> (args) {
	return;
}
```

### IV: Loops

In Symlang all loop keywords are replaced with symbols (much like statements), an example of this is a "while" loop:
```
while true:
	pass

becomes ->

%% (true) {
	return;
}
```
#### All Loops:
"while" loops are called with 
```
%% (args) {
	return;
}
```

"for" loops are called with
```
:: (args) {
	return;
}
```


### V: Syntax
In Symlang comments are done c-style meaning "//" for one-line comments and "/* /" for mutli-line comments.
```
// this is a single line comment

/*
this is a
multi-line
comment
*/
```

Symlang also uses line terminators to denote the end of a line, the line terminator in Symlang is the semi-colon (";").

### VI: Features
**Alarms:**
Alarms are simple but cool features in Symlang, they can be set with `alarm(name).set(on | off)`, they can be read in a "when" statement as `> (alarm(name)) {}`, this allows for code to be triggered without being run.

**When Statements:**
When statements are like signals, they allow parts of the code to trigger things without an if statement based on an updated value, a when statement can be used like this:

```
> (alarm(name)) {
	return;
}
```

When statements can also be used as a sort of constant if statement like this:

```
> (x <= 10) {
	return;
}
```

This can be used in place of calling an if statement after every time you update a variable and allows for less cluttered code. When statements run constantly though so they do impact performance, on variables that **do not** change often we recommend to simply use an if statement after every time you update the variable.
