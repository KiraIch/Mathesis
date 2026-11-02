namespace MathesisPilot
theorem lean_prop_s_combinator : ∀ (P Q R : Prop), (P → Q → R) → (P → Q) → P → R := by
  intro P
  intro Q
  intro R
  intro hPQR
  intro hPQ
  intro hP
  have hQ : Q := hPQ hP
  have hR : R := hPQR hP hQ
  exact hR
end MathesisPilot
