# 3D Frog & Internal Anatomy Assets for XPRISM

This directory contains high-resolution 3D medical biological renders and optimized WebP assets of the Indian bullfrog (*Hoplobatrachus tigerinus* / *Rana tigrina*), created specifically for XPRISM's experimental pharmacology simulations.

---

## 📁 Available Assets

Each asset is provided in both **JPG** (high fidelity) and **WebP** (web-optimized, 90% quality, fast loading):

| File Name (JPG / WebP) | Dimensions | Subject & Anatomical Landmarks | Recommended Module Use |
|---|---|---|---|
| `frog-dorsal-3d` | 1200 × 896 | Intact frog, dorsal view: realistic moist skin, yellow vertebral stripe, marbled flanks, tympanic membranes, splayed webbed hind feet. | Module hero card, frog species selector, pre-lab morphology |
| `frog-ventral-pinned-3d` | 1376 × 768 | Supine frog pinned on black wax dissection tray with metal ball-head pins at all 4 limbs, intact pale ventral skin, dissection instruments on side. | Station 2 initial state (Dissection Tray) in Exp 07 & 12 |
| `frog-internal-anatomy-viscera-3d` | 1200 × 896 | Complete visceral dissection: 3-chambered heart with truncus arteriosus, lungs, multi-lobed liver with gall bladder, J-shaped stomach, coiled intestines, spleen, retroperitoneal structures, branching corpora adiposa (fat bodies). | General anatomical reference, internal anatomy atlas, viva popup |
| `frog-rectus-abdominis-in-situ-3d` | 1376 × 768 | Dissected ventral abdominal wall: pinned lateral skin flaps, paired rectus abdominis strap muscles, glistening central linea alba, transverse tendinous inscriptions (*inscriptiones tendineae*). | Exp 12: Stage 4 (Incision & flap reflection) |
| `frog-rectus-abdominis-prepared-3d` | 1376 × 768 | Rectus abdominis bioassay preparation: braided cotton surgical ligature threads tied with secure knots at both sternal and pubic ends with long tails for organ bath mounting. | Exp 12: Stage 5 (Muscle tied & excised) |
| `frog-oesophagus-ciliary-dissection-3d` | 1200 × 896 | Pharyngeal & oesophageal ciliary motility prep: excised lower jaw, exposed palate, longitudinally slit and pinned mucosal flaps, moist glistening ciliated mucosa, purple indicator START and FINISH lines (20 mm apart). | Exp 07: Station 2 (Slit oesophagus & pinned flaps) |
| `frog-heart-in-situ-3d` | 1200 × 896 | Macro close-up of frog heart in situ: single conical ventricle, bilateral atria, branching truncus arteriosus, reflected pericardial sac, adjacent liver lobes. | Exp on frog heart in situ / cardiac pharmacology |

---

## 🛠️ Claude Integration Guide

### 1. Integration in Experiment 12 (`experiments/12-drc-of-acetylcholine-frog-rectus-abdominis.html`)

In `sceneDissection()` or `drawFrog()`:
Replace the SVG approximation or overlay the 3D render inside `#frogG`:

```html
<!-- Inside Station 2 SVG viewport (1000 x 560): -->
<g id="frogG">
  <!-- Pinned Frog Base / Initial State -->
  <image href="/assets/img/frog/frog-ventral-pinned-3d.webp"
         x="166" y="44" width="668" height="472"
         preserveAspectRatio="xMidYMid meet"
         class="transition-opacity duration-300"/>

  <!-- Swapped when skin flaps reflected (open state) -->
  <image href="/assets/img/frog/frog-rectus-abdominis-in-situ-3d.webp"
         x="166" y="44" width="668" height="472"
         preserveAspectRatio="xMidYMid meet"
         id="imgRectusInSitu" style="display:none;"/>

  <!-- Swapped when threads tied -->
  <image href="/assets/img/frog/frog-rectus-abdominis-prepared-3d.webp"
         x="166" y="44" width="668" height="472"
         preserveAspectRatio="xMidYMid meet"
         id="imgRectusTied" style="display:none;"/>
</g>
```

Dynamic toggle based on simulation state `S.frog`:
- When `!open`: display `frog-ventral-pinned-3d.webp`
- When `open && !F.free`: display `frog-rectus-abdominis-in-situ-3d.webp` or `frog-rectus-abdominis-prepared-3d.webp`
- The existing interactive hotspots (`data-act="pin:*"`, `data-act="lift"`, `data-act="flap:*"`, `data-act="end:*"`) align over the canvas.

---

### 2. Integration in Experiment 07 (`experiments/07-ciliary-motility-of-frog-oesophagus.html`)

In `dyn2()` (Station 2: Dissection):

```html
<!-- Dissection board background overlay -->
<g id="frogG">
  <!-- Before jaw excision & flap pinning -->
  <image href="/assets/img/frog/frog-ventral-pinned-3d.webp"
         x="40" y="26" width="580" height="402"
         preserveAspectRatio="xMidYMid meet"/>

  <!-- When oesophagus is slit & pinned flat (F.slit >= 3 && flaps pinned) -->
  <image href="/assets/img/frog/frog-oesophagus-ciliary-dissection-3d.webp"
         x="40" y="26" width="580" height="402"
         preserveAspectRatio="xMidYMid meet"/>
</g>
```

---

### 3. Anatomical Modal / Reference Tab (Shared Toolkit)

Add an "Anatomy Reference" inspection modal or expandable drawer using `frog-internal-anatomy-viscera-3d.webp` and `frog-heart-in-situ-3d.webp` for student examination and viva training:

```html
<div id="anatomyModal" class="hidden fixed inset-0 z-50 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center p-4">
  <div class="bg-white rounded-2xl max-w-4xl w-full p-6 shadow-2xl border border-slate-200">
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-lg font-bold text-slate-800">Frog Internal Visceral Anatomy (3D Render)</h3>
      <button onclick="$('#anatomyModal').classList.add('hidden')" class="text-slate-400 hover:text-slate-600">✕</button>
    </div>
    <div class="relative rounded-xl overflow-hidden border border-slate-200 bg-slate-950">
      <img src="/assets/img/frog/frog-internal-anatomy-viscera-3d.webp" alt="Frog Internal Visceral Anatomy" class="w-full h-auto object-contain max-h-[65vh] mx-auto"/>
    </div>
    <p class="text-xs text-slate-500 mt-3 text-center">
      Anatomical landmarks: 3-chambered heart (ventricle, atria, truncus arteriosus), multi-lobed liver with gall bladder, J-shaped stomach, small & large intestine, kidneys, fat bodies (corpora adiposa).
    </p>
  </div>
</div>
```
