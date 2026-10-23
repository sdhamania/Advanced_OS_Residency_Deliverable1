#include "shell.hpp"

#include <exception>
#include <iostream>

int main() {
    try {
        Shell shell;
        return shell.run();
    } catch (const std::exception& exception) {
        std::cerr << "os-shell: fatal error: " << exception.what() << '\n';
        return 1;
    }
}

