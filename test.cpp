#include <iostream>
#include <string>

int main() {
    std::string name;
    int score = 0;
    int answer = 0;

    std::cout << "Enter your name: ";
    std::getline(std::cin, name);
    
    std::cout << "\nWelcome, " << name << "! Let's test your math skills.\n\n";

    // Question 1
    std::cout << "Q1: What is 5 + 7?\nYour answer: ";
    std::cin >> answer;
    if (answer == 12) {
        std::cout << "Correct!\n\n";
        score++;
    } else {
        std::cout << "Wrong. The answer is 12.\n\n";
    }

    // Question 2
    std::cout << "Q2: What is 15 - 6?\nYour answer: ";
    std::cin >> answer;
    if (answer == 9) {
        std::cout << "Correct!\n\n";
        score++;
    } else {
        std::cout << "Wrong. The answer is 9.\n\n";
    }

    // Question 3
    std::cout << "Q3: What is 4 * 3?\nYour answer: ";
    std::cin >> answer;
    if (answer == 12) {
        std::cout << "Correct!\n\n";
        score++;
    } else {
        std::cout << "Wrong. The answer is 12.\n\n";
    }

    // Final Score
    std::cout << "Quiz finished! Your total score is: " << score << " out of 3\n";

    return 0;
}
