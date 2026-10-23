CXX ?= c++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -Wpedantic -Werror -O2
CPPFLAGS ?= -Iinclude
PYTHON ?= python3

TARGET := build/os-shell
PARSER_TEST := build/parser-tests
SOURCES := src/main.cpp src/parser.cpp src/shell.cpp
OBJECTS := $(SOURCES:src/%.cpp=build/%.o)

.PHONY: all clean test

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CXX) $(CXXFLAGS) $(OBJECTS) -o $@

build/%.o: src/%.cpp | build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -MMD -MP -c $< -o $@

-include $(OBJECTS:.o=.d)

$(PARSER_TEST): tests/test_parser.cpp src/parser.cpp include/parser.hpp | build
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) tests/test_parser.cpp src/parser.cpp -o $@

build:
	mkdir -p build

test: $(TARGET) $(PARSER_TEST)
	./$(PARSER_TEST)
	$(PYTHON) tests/integration_test.py

clean:
	rm -rf build

