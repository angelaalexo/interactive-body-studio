# Interactive Body Studio

### Procedural 3D human model generation and customization in Blender

**Interactive Body Studio** is a Python-powered Blender application that allows users to generate and customize male and female 3D human models through an interactive interface.

Users can adjust **height, weight, body measurements, proportions, skin type, and clothing** while the model automatically updates inside Blender.


---

## ✨ Features

* 👤 Male & female base models
* 📏 Adjustable height and weight
* 📐 Customizable body measurements
* 🧍 Dynamic body proportion adjustments
* 👕 Clothing selection and management
* 🎨 Skin type customization
* 🔄 Automatic model updates
* 🖥️ Custom Blender interface
* ⚙️ Procedural model customization through Python

---

## 🧠 How It Works

The application uses Blender's Python API to control a customizable base model.

User parameters are exposed through a custom Blender UI:

```text
Height
Weight
Waist
Chest
Hips
Thighs
Skin Type
Clothing
        ↓
Interactive Body Studio
        ↓
Body Parameters
        ↓
Blender Python
        ↓
Body & Clothing Updates
```

Changing a parameter triggers the corresponding model update rather than requiring the model to be manually edited.

---

## 👗 Clothing System

The project also includes a clothing management system designed to work with the generated body models.

Different clothing categories can be selected and managed through the interface, including:

* Tops
* Bottoms
* Male clothing
* Female clothing

The clothing system uses Blender modifiers and deformation techniques to help garments follow the underlying body.

---

## 🧍 Body Customization

The body model can be customized using parameters such as:

| Parameter |    Example |
| --------- | ---------: |
| Height    | 145–190 cm |
| Weight    |   45–90 kg |
| Waist     |   58–82 cm |
| Chest     |  78–100 cm |
| Hips      |  86–108 cm |
| Thighs    | Adjustable |

These parameters are connected to the Blender model through vertex groups and deformation modifiers.

---

## 🖥️ Blender Interface

The application provides a custom Blender panel rather than requiring users to manually modify objects or modifiers.

Example workflow:

```text
Select gender
      ↓
Adjust body parameters
      ↓
Update model
      ↓
Select clothing
      ↓
Update clothing
      ↓
Final customized model
```

---

## 🛠️ Technologies

**Programming**

Python

**3D Development**

Blender · Blender Python API · 3D Modeling · Procedural Modeling

**Blender Systems**

Vertex Groups · Modifiers · Surface Deformation · Shrinkwrap · Shape Keys

---

## 📁 Project Structure

```text
interactive-body-studio/
│
├── body_engine.py
├── clothing/
├── models/
├── scripts/
├── assets/
└── README.md
```

> Update this structure to match the actual repository.

---

## 🎯 Project Goals

The goal of Interactive Body Studio was to explore how **programming can be used to automate and control 3D modeling workflows**.

Instead of manually editing a 3D model for every variation, the application provides a parameter-driven system where changes to body measurements automatically affect the generated model.

---

## 💡 What I Learned

This project gave me experience with:

* Blender's Python API
* Procedural 3D modeling
* Vertex groups and deformation
* Blender modifiers
* Custom Blender UI development
* Managing relationships between body meshes and clothing
* Automating repetitive 3D workflows
* Designing parameter-driven systems

One of the main challenges was keeping the **body and clothing synchronized** as the model's proportions changed. This required experimenting with Blender's deformation and surface-following systems.

---

## 🔮 Future Improvements

* [ ] Improve automatic clothing fitting
* [ ] Add more clothing categories and sizes
* [ ] Improve deformation for extreme body proportions
* [ ] Add more body customization parameters
* [ ] Add animation support
* [ ] Improve garment behavior during animation
* [ ] Export customized models directly from the interface

