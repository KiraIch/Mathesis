namespace MathesisPilot
theorem lean_prop_modus_ponens : ∀ (P Q : Prop), (P → Q) → P → Q := by
  intro P
  intro Q
  intro hPQ
  intro hP
  exact hPQ hP
end MathesisPilot
