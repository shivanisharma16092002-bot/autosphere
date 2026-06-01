import sys
from typing import List
from colorama import init, Fore, Style, Back

# Initialize colorama for Windows/Unix terminal colors
init(autoreset=True)

from models.supplier import Supplier
from models.demand import MarketDemand
from engines.forecasting import forecast_next_demand
from engines.feedback import FeedbackParser
from engines.procurement import ProcurementEngine
from engines.reporting import export_rankings_to_csv, save_supplier_state, load_supplier_state

DEFAULT_STATE_FILE = "suppliers_state.json"

def print_header(title: str):
    print("\n" + "=" * 80)
    print(f"{Fore.CYAN}{Style.BRIGHT}  {title}")
    print("=" * 80)

def print_sub_header(title: str):
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}>>> {title}")
    print("-" * 50)

def display_supplier_table(suppliers: List[Supplier], title: str = "CURRENT SUPPLIERS"):
    print_sub_header(title)
    header = f"{'ID':<4} | {'Name':<22} | {'Location':<18} | {'Component':<12} | {'Cost ($)':<8} | {'Risk':<5} | {'Capacity':<8}"
    print(f"{Fore.BLUE}{Style.BRIGHT}{header}")
    print("-" * 88)
    for s in suppliers:
        if s.risk_score < 0.15:
            risk_color = Fore.GREEN
        elif s.risk_score < 0.35:
            risk_color = Fore.YELLOW
        else:
            risk_color = Fore.RED
            
        row = f"{s.id:<4} | {s.name:<22} | {s.location:<18} | {s.component_type:<12} | ${s.base_cost:<7.2f} | {risk_color}{s.risk_score:<5.2f}{Style.RESET_ALL} | {s.capacity:<8,}"
        print(row)
    print("-" * 88)

def run_standard_simulation(suppliers: List[Supplier], demand_profile: MarketDemand, feedbacks: List[str]):
    """
    Executes the original automated simulation lifecycle.
    """
    print("\n" + Back.BLUE + Fore.WHITE + Style.BRIGHT + " " * 28 + "AUTOSPHERE AI PLATFORM" + " " * 30)
    print(Fore.BLUE + Style.BRIGHT + "========================================= RUNNING STANDARD SIMULATION =================================")

    # Display Initial Suppliers
    display_supplier_table(suppliers, "INITIAL GLOBAL SUPPLIERS POOL")

    # 1. DEMAND FORECASTING ENGINE
    print_header("STAGE 1: DEMAND FORECASTING ENGINE")
    print(f"Target Component: {Fore.MAGENTA}{Style.BRIGHT}{demand_profile.component_type}")
    print(f"Historical Demand: {Fore.GREEN}{Style.BRIGHT}{demand_profile.historical_demand}")
    
    forecasted_value = forecast_next_demand(demand_profile.historical_demand)
    
    last_value = demand_profile.historical_demand[-1]
    trend_pct = ((forecasted_value - last_value) / last_value) * 100
    trend_arrow = "[UP]" if trend_pct > 0 else "[DOWN]"
    trend_color = Fore.GREEN if trend_pct > 0 else Fore.RED
    
    print(f"\nForecast for Next Month: {Fore.CYAN}{Style.BRIGHT}{forecasted_value:,} units")
    print(f"Projected Month-over-Month Trend: {trend_color}{Style.BRIGHT}{trend_arrow} {abs(trend_pct):.2f}%")
    print(f"Contractual Required Quantity: {Fore.WHITE}{Style.BRIGHT}{demand_profile.required_quantity:,} units")
    
    total_matching_capacity = sum(s.capacity for s in suppliers if s.component_type.lower() == demand_profile.component_type.lower())
    print(f"Total matching suppliers capacity: {Fore.WHITE}{Style.BRIGHT}{total_matching_capacity:,} units")
    
    if forecasted_value > total_matching_capacity:
        print(f"{Fore.RED}{Style.BRIGHT}[WARNING] Projected demand exceeds total supplier capacity by {forecasted_value - total_matching_capacity:,} units!")
    else:
        print(f"{Fore.GREEN}{Style.BRIGHT}[SUCCESS] Sufficient aggregate supplier capacity available.")

    # 2. NLP FEEDBACK PARSER ENGINE
    print_header("STAGE 2: NLP CUSTOMER FEEDBACK & RISK ENGINE")
    print(f"Processing customer feedback streams and dynamically updating supplier risk scores...\n")
    
    parser = FeedbackParser(suppliers)
    
    for idx, fb in enumerate(feedbacks, 1):
        parsed = parser.parse_feedback(fb)
        print(f"{Fore.BLUE}{Style.BRIGHT}Feedback #{idx}:{Style.RESET_ALL} \"{fb}\"")
        
        if parsed["matched_supplier"]:
            print(f"  * {Fore.GREEN}Matched Supplier: {Fore.WHITE}{Style.BRIGHT}{parsed['matched_supplier']} ({parsed['supplier_id']})")
            print(f"  * {Fore.GREEN}Matched Component: {Fore.WHITE}{Style.BRIGHT}{parsed['matched_component']}")
            print(f"  * {Fore.YELLOW}Risk Keywords: {Fore.WHITE}{parsed['detected_keywords']}")
            
            severity_color = Fore.WHITE
            if parsed["sentiment_severity"] == "critical":
                severity_color = Fore.RED + Style.BRIGHT
            elif parsed["sentiment_severity"] == "severe":
                severity_color = Fore.RED
            elif parsed["sentiment_severity"] == "moderate":
                severity_color = Fore.YELLOW
                
            print(f"  * {Fore.YELLOW}Detected Severity: {severity_color}{parsed['sentiment_severity'].upper()}")
            print(f"  * {Fore.RED}Risk Penalty Added: {Fore.WHITE}{Style.BRIGHT}+{parsed['risk_penalty']:.2f}")
            print(f"  * {Fore.CYAN}Risk Adjustment: {Fore.WHITE}{parsed['old_risk_score']:.2f} ---> {Fore.RED}{Style.BRIGHT}{parsed['new_risk_score']:.2f}")
        else:
            print(f"  * {Fore.RED}No matching supplier detected in this feedback string.")
        print("-" * 80)

    # Persist live state post feedback updates
    save_supplier_state(suppliers, DEFAULT_STATE_FILE)

    # Display updated state of suppliers
    display_supplier_table(suppliers, "UPDATED SUPPLIER POOL (POST-FEEDBACK RISK UPDATES)")

    # 3. PROCUREMENT ENGINE (OPTIMIZATION)
    print_header("STAGE 3: MULTI-CRITERIA PROCUREMENT ENGINE")
    print(f"Optimizing sourcing strategy for Component Type: {Fore.MAGENTA}{Style.BRIGHT}{demand_profile.component_type}")
    print(f"Weight Configuration: {Fore.WHITE}Cost (40%) | Risk (40%) | Capacity (20%)")
    
    procurement_engine = ProcurementEngine(suppliers)
    rankings = procurement_engine.optimize_sourcing(demand_profile.component_type)
    
    run_and_display_sourcing_rankings(rankings, demand_profile.component_type, auto_export=True)

def run_and_display_sourcing_rankings(rankings, component_type: str, auto_export: bool = False):
    if not rankings:
        print(f"{Fore.RED}{Style.BRIGHT}[ERROR] No matching suppliers found for component type '{component_type}'")
        return
        
    print_sub_header("SUPPLIER EVALUATION RANKINGS")
    
    header = f"{'Rank':<4} | {'Supplier Name':<20} | {'Base Cost':<9} | {'Capacity':<8} | {'Cost Sc':<7} | {'Risk Sc':<7} | {'Cap Sc':<6} | {'Composite Score'}"
    print(f"{Fore.BLUE}{Style.BRIGHT}{header}")
    print("-" * 92)
    
    for rank, item in enumerate(rankings, 1):
        s = item["supplier"]
        name = s.name
        cost = f"${s.base_cost:.2f}"
        cap = f"{s.capacity:,}"
        
        row_color = Fore.WHITE
        if rank == 1:
            row_color = Fore.GREEN + Style.BRIGHT
            rank_str = f"{Fore.GREEN}{Style.BRIGHT}#1"
        else:
            rank_str = f"#{rank}"
            
        row = (
            f"{rank_str:<4} | {row_color}{name:<20}{Style.RESET_ALL} | "
            f"{cost:<9} | {cap:<8} | "
            f"{item['cost_score']:<7.2f} | {item['risk_score']:<7.2f} | {item['capacity_score']:<6.2f} | "
            f"{row_color}{item['composite_score']:.4f}"
        )
        print(row)
    print("-" * 92)

    winner_item = rankings[0]
    winner = winner_item["supplier"]
    
    print("\n" + "*" * 80)
    print(f" {Back.GREEN}{Fore.BLACK}{Style.BRIGHT}  SOURCING RECOMMENDATION DECISION  ")
    print("*" * 80)
    print(f" Recommended Supplier : {Fore.GREEN}{Style.BRIGHT}{winner.name} ({winner.id})")
    print(f" Sourcing Location     : {Fore.WHITE}{winner.location}")
    print(f" Base Component Cost  : {Fore.WHITE}${winner.base_cost:.2f}")
    print(f" Current Risk Score   : {Fore.RED if winner.risk_score > 0.4 else Fore.YELLOW if winner.risk_score > 0.15 else Fore.GREEN}{winner.risk_score:.2f}")
    print(f" Monthly Capacity     : {Fore.WHITE}{winner.capacity:,} units")
    print(f" Optimization Score   : {Fore.GREEN}{Style.BRIGHT}{winner_item['composite_score']:.4f}")
    print("*" * 80)

    # Export report if requested/automatic
    if auto_export:
        filepath = export_rankings_to_csv(rankings)
        print(f"\n{Fore.GREEN}[REPORT] Automatically exported sourcing optimization results to CSV:")
        print(f"         {Fore.CYAN}{filepath}")
    else:
        export_choice = input(f"\n{Fore.YELLOW}Export these evaluation rankings to a CSV spreadsheet? (y/n) [y]: {Style.RESET_ALL}").strip().lower()
        if export_choice in ["", "y", "yes"]:
            filepath = export_rankings_to_csv(rankings)
            print(f"{Fore.GREEN}[SUCCESS] Saved sourcing report to: {Fore.CYAN}{filepath}")


def get_default_suppliers() -> List[Supplier]:
    return [
        Supplier(id="S1", name="Apex Parts Corp", location="Detroit, USA", component_type="Brake Pads", base_cost=45.00, risk_score=0.15, capacity=10000),
        Supplier(id="S2", name="Vertex Automotive", location="Munich, Germany", component_type="Brake Pads", base_cost=48.00, risk_score=0.08, capacity=12000),
        Supplier(id="S3", name="Zephyr Braking Co", location="Shanghai, China", component_type="Brake Pads", base_cost=38.00, risk_score=0.35, capacity=8000),
        Supplier(id="S4", name="Quantum Tech Inc", location="Tokyo, Japan", component_type="Microchips", base_cost=12.50, risk_score=0.05, capacity=50000),
        Supplier(id="S5", name="GlobalTech Solutions", location="Seoul, South Korea", component_type="Microchips", base_cost=11.00, risk_score=0.20, capacity=45000)
    ]

def interactive_dashboard(suppliers: List[Supplier], demand_profile: MarketDemand):
    parser = FeedbackParser(suppliers)
    procurement_engine = ProcurementEngine(suppliers)
    
    while True:
        print("\n" + "=" * 80)
        print(f" {Back.CYAN}{Fore.BLACK}{Style.BRIGHT}                 AUTOSPHERE AI CONTROL DASHBOARD                 ")
        print("=" * 80)
        print(f" {Fore.GREEN}1.{Style.RESET_ALL} Display Current Supplier Pool")
        print(f" {Fore.GREEN}2.{Style.RESET_ALL} Input Custom Customer Feedback (NLP Risk Adjuster)")
        print(f" {Fore.GREEN}3.{Style.RESET_ALL} Run Sourcing Procurement Optimization")
        print(f" {Fore.GREEN}4.{Style.RESET_ALL} Re-configure Sourcing Weight Ratios")
        print(f" {Fore.GREEN}5.{Style.RESET_ALL} Forecast Inventory Demand")
        print(f" {Fore.GREEN}6.{Style.RESET_ALL} Add a New Supplier to Pool")
        print(f" {Fore.GREEN}7.{Style.RESET_ALL} Reset Supplier Database to Factory Defaults")
        print(f" {Fore.GREEN}8.{Style.RESET_ALL} Exit Program")
        print("-" * 80)
        
        choice = input(f"{Fore.YELLOW}{Style.BRIGHT}Select dashboard control parameter (1-8): {Style.RESET_ALL}").strip()
        
        if choice == "1":
            display_supplier_table(suppliers, "LIVE GLOBAL SUPPLIER POOL")
            
        elif choice == "2":
            print_sub_header("REAL-TIME CUSTOMER FEEDBACK NLP SIMULATION")
            print(f"Provide unstructured feedback (e.g. 'Brake pads from Vertex Automotive had critical recall defects and delay issues'):")
            fb_text = input(f"{Fore.CYAN}Feedback Text > {Style.RESET_ALL}").strip()
            
            if not fb_text:
                print(f"{Fore.RED}Operation cancelled. Empty string provided.")
                continue
                
            parsed = parser.parse_feedback(fb_text)
            print("\n" + "-" * 50)
            print(f"{Fore.GREEN}{Style.BRIGHT}NLP Semantic Interpretation Output:")
            
            if parsed["matched_supplier"]:
                print(f" * Matched Supplier  : {Fore.WHITE}{Style.BRIGHT}{parsed['matched_supplier']} ({parsed['supplier_id']})")
                print(f" * Matched Component : {Fore.WHITE}{parsed['matched_component']}")
                print(f" * Risk Keywords     : {Fore.YELLOW}{parsed['detected_keywords']}")
                print(f" * Sentiment Severity: {Fore.RED if parsed['sentiment_severity'] in ['critical', 'severe'] else Fore.YELLOW}{parsed['sentiment_severity'].upper()}")
                print(f" * Penalty Added     : {Fore.RED}{Style.BRIGHT}+{parsed['risk_penalty']:.2f}")
                print(f" * Updated Risk Index: {Fore.WHITE}{parsed['old_risk_score']:.2f} ---> {Fore.RED}{Style.BRIGHT}{parsed['new_risk_score']:.2f}")
                
                # Save live state to file
                save_supplier_state(suppliers, DEFAULT_STATE_FILE)
            else:
                print(f" * {Fore.RED}No matching supplier identified in this text. Risk profile unchanged.")
            print("-" * 50)
            
        elif choice == "3":
            print_sub_header("LIVE PROCUREMENT OPTIMIZATION SOLVER")
            comp_type = input(f"{Fore.CYAN}Enter Component Type (e.g. Brake Pads, Microchips) [{demand_profile.component_type}]: {Style.RESET_ALL}").strip()
            if not comp_type:
                comp_type = demand_profile.component_type
                
            print(f"\nEvaluating candidates matching component '{comp_type}' under current scoring configurations:")
            print(f"Cost Weight     : {procurement_engine.WEIGHT_COST:.2%}")
            print(f"Risk Weight     : {procurement_engine.WEIGHT_RISK:.2%}")
            print(f"Capacity Weight : {procurement_engine.WEIGHT_CAPACITY:.2%}")
            
            rankings = procurement_engine.optimize_sourcing(comp_type)
            run_and_display_sourcing_rankings(rankings, comp_type, auto_export=False)
            
        elif choice == "4":
            print_sub_header("OPTIMIZATION WEIGHT CONFIGURATION")
            print(f"Current allocation: Cost: {procurement_engine.WEIGHT_COST:.1f}, Risk: {procurement_engine.WEIGHT_RISK:.1f}, Capacity: {procurement_engine.WEIGHT_CAPACITY:.1f}")
            
            try:
                c_w = float(input(f"{Fore.CYAN}Enter new Cost Weight (e.g. 0.35) [current {procurement_engine.WEIGHT_COST}]: {Style.RESET_ALL}") or procurement_engine.WEIGHT_COST)
                r_w = float(input(f"{Fore.CYAN}Enter new Risk Weight (e.g. 0.45) [current {procurement_engine.WEIGHT_RISK}]: {Style.RESET_ALL}") or procurement_engine.WEIGHT_RISK)
                cap_w = float(input(f"{Fore.CYAN}Enter new Capacity Weight (e.g. 0.20) [current {procurement_engine.WEIGHT_CAPACITY}]: {Style.RESET_ALL}") or procurement_engine.WEIGHT_CAPACITY)
                
                w_sum = c_w + r_w + cap_w
                if abs(w_sum - 1.0) > 1e-4:
                    print(f"{Fore.RED}[ERROR] Weights must sum up to exactly 1.0! Current input sum = {w_sum:.4f}. Resetting defaults.")
                else:
                    procurement_engine.WEIGHT_COST = round(c_w, 4)
                    procurement_engine.WEIGHT_RISK = round(r_w, 4)
                    procurement_engine.WEIGHT_CAPACITY = round(cap_w, 4)
                    print(f"{Fore.GREEN}[SUCCESS] Procurement solver weight ratios updated successfully!")
            except ValueError:
                print(f"{Fore.RED}[ERROR] Invalid numerical input format. Reverting weights.")
                
        elif choice == "5":
            print_sub_header("DEMAND FORECAST SOLVER")
            print(f"Active demand series: {Fore.GREEN}{demand_profile.historical_demand}")
            forecasted = forecast_next_demand(demand_profile.historical_demand)
            print(f"Predicted Next Month's Quantity requirement: {Fore.CYAN}{Style.BRIGHT}{forecasted:,} units")
            
        elif choice == "6":
            print_sub_header("REGISTER NEW INVENTORY SUPPLIER CANDIDATE")
            try:
                sup_id = f"S{len(suppliers) + 1}"
                name = input(f"{Fore.CYAN}Company Name: {Style.RESET_ALL}").strip()
                loc = input(f"{Fore.CYAN}Location: {Style.RESET_ALL}").strip()
                comp = input(f"{Fore.CYAN}Component Type Supplied (e.g. Brake Pads, Microchips): {Style.RESET_ALL}").strip()
                cost = float(input(f"{Fore.CYAN}Base Component Cost ($): {Style.RESET_ALL}"))
                risk = float(input(f"{Fore.CYAN}Initial Risk Score (0.0 to 1.0): {Style.RESET_ALL}"))
                cap = int(input(f"{Fore.CYAN}Monthly Product Capacity (units): {Style.RESET_ALL}"))
                
                new_supplier = Supplier(
                    id=sup_id,
                    name=name,
                    location=loc,
                    component_type=comp,
                    base_cost=cost,
                    risk_score=risk,
                    capacity=cap
                )
                suppliers.append(new_supplier)
                save_supplier_state(suppliers, DEFAULT_STATE_FILE)
                print(f"{Fore.GREEN}{Style.BRIGHT}[SUCCESS] Registered new supplier candidate {name} successfully assigned as unique ID: {sup_id}")
            except (ValueError, Exception) as e:
                print(f"{Fore.RED}[ERROR] Validation Error: Failed to register supplier. Details: {e}")
                
        elif choice == "7":
            print_sub_header("RESET SUPPLIER DATABASE STATE")
            confirm = input(f"{Fore.RED}{Style.BRIGHT}Warning: This resets all custom risk adjustments and new entries. Confirm? (y/n): {Style.RESET_ALL}").strip().lower()
            if confirm in ["y", "yes"]:
                # Clear standard state
                suppliers.clear()
                suppliers.extend(get_default_suppliers())
                save_supplier_state(suppliers, DEFAULT_STATE_FILE)
                # Re-initialize the engines
                parser.suppliers = suppliers
                procurement_engine.suppliers = suppliers
                print(f"{Fore.GREEN}[SUCCESS] Supplier database restored back to standard factory mock levels.")
            else:
                print(f"{Fore.YELLOW}Reset operation cancelled.")

        elif choice == "8":
            print(f"\n{Fore.GREEN}{Style.BRIGHT}Gracefully shutting down AutoSphere AI decision panel. Sourcing logs saved. Goodbye!")
            sys.exit(0)
            
        else:
            print(f"{Fore.RED}Invalid menu argument. Please supply an option between 1 and 8.")

def main():
    # 1. Try loading database state, fallback to default
    suppliers = load_supplier_state(DEFAULT_STATE_FILE)
    if not suppliers:
        suppliers = get_default_suppliers()
        save_supplier_state(suppliers, DEFAULT_STATE_FILE)

    demand_profile = MarketDemand(
        component_type="Brake Pads",
        target_cost=42.00,
        required_quantity=9500,
        historical_demand=[8200, 8500, 8700, 8900, 9200, 9400]
    )

    feedbacks = [
        "The brake pads from Zephyr Braking Co are wearing out too fast during high-speed deceleration tests, causing a dangerous squeal.",
        "We experienced a major recall and safety defect on brake pads shipped by Apex Parts Corp last week. It was a severe defect.",
        "Quantum Tech Inc provided stellar support, but their microchips are experiencing some delay in delivery due to logistics issues."
    ]

    # Run standard mock simulation
    run_standard_simulation(suppliers, demand_profile, feedbacks)
    
    print(f"\n{Fore.GREEN}{Style.BRIGHT}============================= SIMULATION RUN COMPLETED =============================\n")
    print(f"{Fore.YELLOW}Press ENTER to transition into the Interactive Control Dashboard...")
    input()
    
    interactive_dashboard(suppliers, demand_profile)

if __name__ == "__main__":
    main()
