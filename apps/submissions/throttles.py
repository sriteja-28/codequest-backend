from rest_framework.throttling import UserRateThrottle

class RunThrottle(UserRateThrottle):
    """Rate limit for Run endpoint (sample test cases only)"""
    
    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        user_id = request.user.id
        plan = 'pro' if request.user.is_pro else 'free'
        return f'throttle_run_{plan}_{user_id}'
    
    def get_rate(self):
        if not hasattr(self, 'request') or not self.request.user.is_authenticated:
            return '5/hour'
        return 'run_pro' if self.request.user.is_pro else 'run_free'


class SubmitThrottle(UserRateThrottle):
    """Rate limit for Submit endpoint (full judge)"""
    
    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        user_id = request.user.id
        plan = 'pro' if request.user.is_pro else 'free'
        return f'throttle_submit_{plan}_{user_id}'
    
    def get_rate(self):
        if not hasattr(self, 'request') or not self.request.user.is_authenticated:
            return '3/hour'
        return 'submit_pro' if self.request.user.is_pro else 'submit_free'


class BurstThrottle(UserRateThrottle):
    """Prevent rapid-fire clicks"""
    
    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        return f'throttle_burst_{request.user.id}'
    
    def get_rate(self):
        return '5/minute'