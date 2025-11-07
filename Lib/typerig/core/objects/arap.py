# MODULE: TypeRig / Core / ARAP (Object)
# Note: As-Rigid-As-Possible deformation for font contours
# -----------------------------------------------------------
# (C) Vassil Kateliev, 2025         (http://www.kateliev.com)
# (C) Karandash Type Foundry        (http://www.karandash.eu)
#------------------------------------------------------------
# www.typerig.com

# No warranties. By using this you agree
# that you use it at your own risk!

# - Dependencies ------------------------
import math

from point import Point
from node import Node
from contour import Contour
from matrix import Mat, Vec, eye

# - Init -------------------------------
__version__ = '0.1.0'

# - Helper Functions -------------------------
def distance_squared(p1, p2):
    """Squared distance between two Point objects"""
    dx = p1.x - p2.x
    dy = p1.y - p2.y
    return dx * dx + dy * dy

def find_k_nearest(point, all_points, k, exclude_index=None):
    """Find k nearest neighbors of a point"""
    distances = []
    for i, p in enumerate(all_points):
        if exclude_index is not None and i == exclude_index:
            continue
        dist = distance_squared(point, p)
        distances.append((dist, i))
    
    distances.sort()
    return [idx for dist, idx in distances[:k]]

def compute_rotation_2d(S_matrix):
    """
    Compute 2D rotation from 2x2 covariance matrix
    Uses simplified SVD approach for 2D case
    
    Args:
        S_matrix: Mat([[a, b], [c, d]]) - 2x2 covariance matrix
    
    Returns:
        Mat - 2x2 rotation matrix
    """
    S = S_matrix
    
    # Compute S^T * S
    StS_a = S[0][0] * S[0][0] + S[1][0] * S[1][0]
    StS_b = S[0][0] * S[0][1] + S[1][0] * S[1][1]
    StS_c = S[0][1] * S[0][0] + S[1][1] * S[1][0]
    StS_d = S[0][1] * S[0][1] + S[1][1] * S[1][1]
    
    # Eigenvalues of symmetric 2x2 matrix
    trace = StS_a + StS_d
    det = StS_a * StS_d - StS_b * StS_c
    
    discriminant = trace * trace - 4 * det
    if discriminant < 0:
        discriminant = 0
    
    sqrt_disc = math.sqrt(discriminant)
    lambda1 = (trace + sqrt_disc) / 2
    lambda2 = (trace - sqrt_disc) / 2
    
    # Check for degenerate case
    if lambda1 < 1e-10 or lambda2 < 1e-10:
        return eye(2)  # Identity matrix
    
    # Simplified rotation extraction
    angle = math.atan2(S[1][0] + S[1][1], S[0][0] + S[0][1]) - \
            math.atan2(math.sqrt(lambda2), math.sqrt(lambda1))
    
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    
    R = Mat([[cos_a, -sin_a], 
             [sin_a, cos_a]])
    
    # Ensure proper rotation (no reflection)
    if R[0][0] * R[1][1] - R[0][1] * R[1][0] < 0:
        R[0][0] = -R[0][0]
        R[1][0] = -R[1][0]
    
    return R


# - Main ARAP Class --------------------------
class ARAPDeformer:
    """
    As-Rigid-As-Possible deformation for 2D contours
    Maintains local rigidity while allowing global transformation
    """
    
    def __init__(self, points, k_neighbors=6):
        """
        Initialize ARAP deformer
        
        Args:
            points: list of Point objects or Contour
            k_neighbors: number of neighbors for each point
        """
        # Extract points
        if isinstance(points, Contour):
            self.points = [node.point for node in points.nodes]
        elif isinstance(points, list) and len(points) > 0:
            if isinstance(points[0], Node):
                self.points = [node.point for node in points]
            elif isinstance(points[0], Point):
                self.points = [Point(p.x, p.y) for p in points]
            elif isinstance(points[0], (tuple, list)):
                self.points = [Point(p[0], p[1]) for p in points]
            else:
                raise ValueError("Unsupported point type")
        else:
            raise ValueError("Points must be a Contour, list of Nodes, Points, or tuples")
        
        self.n_points = len(self.points)
        self.k_neighbors = k_neighbors
        
        # Build data structures
        self.neighbors = self._build_neighborhoods()
        self.weights = self._compute_weights()
    
    def _build_neighborhoods(self):
        """Build k-nearest neighbor graph"""
        neighbors = []
        
        for i in range(self.n_points):
            # Get k nearest neighbors
            neighbor_indices = find_k_nearest(
                self.points[i], 
                self.points, 
                self.k_neighbors,
                exclude_index=i
            )
            
            # Add topological neighbors (for closed contours)
            prev_idx = (i - 1) % self.n_points
            next_idx = (i + 1) % self.n_points
            
            if prev_idx not in neighbor_indices:
                neighbor_indices.append(prev_idx)
            if next_idx not in neighbor_indices:
                neighbor_indices.append(next_idx)
            
            neighbors.append(neighbor_indices)
        
        return neighbors
    
    def _compute_weights(self):
        """Compute edge weights (uniform for simplicity)"""
        weights = []
        for i in range(self.n_points):
            w = {}
            for j in self.neighbors[i]:
                # Could use cotangent weights for better quality
                # For now: uniform weights
                w[j] = 1.0
            weights.append(w)
        return weights
    
    def _compute_local_rotation(self, i, current_points):
        """
        Compute optimal rotation for point i that best preserves
        the shape of its neighborhood
        """
        p_i = self.points[i]
        p_i_prime = current_points[i]
        
        # Build covariance matrix S = Σ w_ij * e_ij * e'_ij^T
        S_data = [[0.0, 0.0], [0.0, 0.0]]
        
        for j in self.neighbors[i]:
            w_ij = self.weights[i][j]
            
            # Original edge
            e_ij = self.points[j] - p_i
            
            # Current edge
            e_ij_prime = current_points[j] - p_i_prime
            
            # Outer product: e_ij * e_ij_prime^T
            S_data[0][0] += w_ij * e_ij.x * e_ij_prime.x
            S_data[0][1] += w_ij * e_ij.x * e_ij_prime.y
            S_data[1][0] += w_ij * e_ij.y * e_ij_prime.x
            S_data[1][1] += w_ij * e_ij.y * e_ij_prime.y
        
        S = Mat(S_data)
        
        # Extract rotation from covariance matrix
        R = compute_rotation_2d(S)
        
        return R
    
    def _apply_rotation_to_vector(self, R, v):
        """Apply rotation matrix R to vector v (Point)"""
        # R is Mat 2x2, v is Point
        x_new = R[0][0] * v.x + R[0][1] * v.y
        y_new = R[1][0] * v.x + R[1][1] * v.y
        return Point(x_new, y_new)
    
    def _solve_positions_gauss_seidel(self, free_indices, rotations, 
                                       current_points, constraints, 
                                       max_inner_iter=50):
        """
        Solve for new positions using Gauss-Seidel iteration
        
        This is simpler than full sparse matrix solver but still effective
        """
        # Create a copy of current points
        new_points = [Point(p.x, p.y) for p in current_points]
        
        # Create set for fast lookup
        free_set = set(free_indices)
        
        # Gauss-Seidel iterations
        for iteration in range(max_inner_iter):
            max_change = 0.0
            
            for i in free_indices:
                # Compute right-hand side for point i
                rhs_x = 0.0
                rhs_y = 0.0
                w_sum = 0.0
                
                for j in self.neighbors[i]:
                    w_ij = self.weights[i][j]
                    w_sum += w_ij
                    
                    # Add neighbor contribution
                    if j in free_set:
                        rhs_x += w_ij * new_points[j].x
                        rhs_y += w_ij * new_points[j].y
                    elif j in constraints:
                        rhs_x += w_ij * constraints[j].x
                        rhs_y += w_ij * constraints[j].y
                    else:
                        rhs_x += w_ij * current_points[j].x
                        rhs_y += w_ij * current_points[j].y
                    
                    # Add rotation term: 0.5 * w_ij * (R_i * e_ij + R_j * (-e_ij))
                    R_i = rotations[i]
                    R_j = rotations[j]
                    e_ij = self.points[j] - self.points[i]
                    
                    rot_i_term = self._apply_rotation_to_vector(R_i, e_ij)
                    rot_j_term = self._apply_rotation_to_vector(R_j, e_ij * -1)
                    
                    rhs_x += 0.5 * w_ij * (rot_i_term.x + rot_j_term.x)
                    rhs_y += 0.5 * w_ij * (rot_i_term.y + rot_j_term.y)
                
                # Update position
                old_x, old_y = new_points[i].x, new_points[i].y
                new_points[i].x = rhs_x / w_sum
                new_points[i].y = rhs_y / w_sum
                
                # Track convergence
                change = abs(new_points[i].x - old_x) + abs(new_points[i].y - old_y)
                max_change = max(max_change, change)
            
            # Check for convergence
            if max_change < 1e-4:
                break
        
        return new_points
    
    def deform(self, constraints, max_iterations=20, verbose=False):
        """
        Apply ARAP deformation with given constraints
        
        Args:
            constraints: dict {point_index: Point or (x, y) tuple}
            max_iterations: number of outer iterations
            verbose: print convergence info
        
        Returns:
            list of Point objects with deformed positions
        """
        # Initialize with original positions
        current_points = [Point(p.x, p.y) for p in self.points]
        
        # Convert constraints to Point objects
        constraints_pts = {}
        for idx, pos in constraints.items():
            if isinstance(pos, Point):
                constraints_pts[idx] = Point(pos.x, pos.y)
            elif isinstance(pos, (tuple, list)):
                constraints_pts[idx] = Point(pos[0], pos[1])
            else:
                raise ValueError(f"Constraint must be Point or tuple, got {type(pos)}")
        
        # Determine free indices
        free_indices = [i for i in range(self.n_points) if i not in constraints_pts]
        
        if len(free_indices) == 0:
            # All points constrained
            for idx, pos in constraints_pts.items():
                current_points[idx] = pos
            return current_points
        
        # Main ARAP iteration loop
        for iteration in range(max_iterations):
            # Step 1: Compute local rotations for all points
            rotations = []
            for i in range(self.n_points):
                R = self._compute_local_rotation(i, current_points)
                rotations.append(R)
            
            # Step 2: Solve for new positions
            prev_points = [Point(p.x, p.y) for p in current_points]
            
            current_points = self._solve_positions_gauss_seidel(
                free_indices, 
                rotations, 
                current_points, 
                constraints_pts
            )
            
            # Apply constraints
            for idx, pos in constraints_pts.items():
                current_points[idx] = Point(pos.x, pos.y)
            
            # Check convergence
            total_diff = sum(
                abs(current_points[i] - prev_points[i])
                for i in range(self.n_points)
            )
            
            if verbose:
                print(f"Iteration {iteration + 1}: total_diff = {total_diff:.6f}")
            
            if total_diff < 1e-3:
                if verbose:
                    print(f"Converged after {iteration + 1} iterations")
                break
        
        return current_points


# - Convenience Functions --------------------
def arap_scale_contour(contour, scale_x=1.5, scale_y=1.0, 
                       stem_indices=None, stem_preserve=0.2,
                       k_neighbors=6, max_iterations=20, verbose=False):
    """
    Scale a contour using ARAP while preserving stem widths
    
    Args:
        contour: Contour object or list of Points/Nodes
        scale_x, scale_y: scaling factors
        stem_indices: list of indices on stems to preserve
        stem_preserve: how much to preserve stems (0=full scale, 1=no scale)
        k_neighbors: neighborhood size for ARAP
        max_iterations: ARAP iterations
        verbose: print debug info
    
    Returns:
        list of Point objects with new positions
    """
    # Initialize deformer
    deformer = ARAPDeformer(contour, k_neighbors=k_neighbors)
    
    # Compute center
    points = deformer.points
    center = Point(
        sum(p.x for p in points) / len(points),
        sum(p.y for p in points) / len(points)
    )
    
    # Build constraints
    constraints = {}
    
    if stem_indices and len(stem_indices) > 0:
        # Constrain stem points to move less
        for i in stem_indices:
            p = points[i]
            p_rel = p - center
            
            # Partial scaling for stems
            stem_scale_x = 1.0 + stem_preserve * (scale_x - 1.0)
            stem_scale_y = 1.0 + stem_preserve * (scale_y - 1.0)
            
            p_new = center + Point(p_rel.x * stem_scale_x, p_rel.y * stem_scale_y)
            constraints[i] = p_new
    else:
        # Use corner points (extremes) as constraints
        distances = [abs(p - center) for p in points]
        corner_indices = sorted(range(len(distances)), 
                               key=lambda i: distances[i], 
                               reverse=True)[:4]
        
        for i in corner_indices:
            p = points[i]
            p_rel = p - center
            p_new = center + Point(p_rel.x * scale_x, p_rel.y * scale_y)
            constraints[i] = p_new
    
    # Apply ARAP deformation
    deformed_points = deformer.deform(
        constraints, 
        max_iterations=max_iterations,
        verbose=verbose
    )
    
    return deformed_points


def apply_arap_to_contour(contour, deformed_points):
    """
    Apply deformed points back to a contour object
    
    Args:
        contour: Contour object to modify
        deformed_points: list of Point objects from ARAP
    """
    if not isinstance(contour, Contour):
        raise ValueError("First argument must be a Contour object")
    
    if len(deformed_points) != len(contour.nodes):
        raise ValueError("Number of deformed points must match contour nodes")
    
    for i, node in enumerate(contour.nodes):
        node.x = deformed_points[i].x
        node.y = deformed_points[i].y


# - Test/Example -----------------------------
if __name__ == '__main__':
    # Example: Create a simple rectangle and scale it
    print("Testing ARAP deformation...")
    
    # Create rectangle points
    rect_points = [
        Point(0, 0),
        Point(100, 0),
        Point(100, 500),
        Point(0, 500)
    ]
    
    print("Original points:")
    for i, p in enumerate(rect_points):
        print(f"  {i}: {p}")
    
    # Apply ARAP scaling
    stem_indices = [0, 1]  # Bottom edge should be preserved
    
    deformed = arap_scale_contour(
        rect_points,
        scale_x=1.5,
        scale_y=1.0,
        stem_indices=stem_indices,
        stem_preserve=0.8,  # Preserve 80% of stem
        verbose=True
    )
    
    print("\nDeformed points:")
    for i, p in enumerate(deformed):
        print(f"  {i}: ({p.x:.2f}, {p.y:.2f})")
