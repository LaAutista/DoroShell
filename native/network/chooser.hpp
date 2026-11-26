#pragma once
#include "model.hpp"
#include <QWidget>

void styleChooser();
std::unique_ptr<QWidget> createChooser(std::shared_ptr<NMClient> client);
